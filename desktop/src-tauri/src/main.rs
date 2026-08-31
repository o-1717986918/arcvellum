use std::{
    fs,
    io::{Read, Write},
    net::TcpStream,
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use tauri::{path::BaseDirectory, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};
use uuid::Uuid;

#[cfg(target_os = "windows")]
const PI_WORKER_NODE: &str = "resources/pi-worker/node.exe";
#[cfg(target_os = "macos")]
const PI_WORKER_NODE: &str = "resources/pi-worker/node";
#[cfg(not(any(target_os = "windows", target_os = "macos")))]
const PI_WORKER_NODE: &str = "resources/pi-worker/node";

struct StudioSidecar(Mutex<Option<CommandChild>>);

fn emit_startup_error(window: &WebviewWindow, message: &str) {
    let payload = serde_json::json!({ "message": message });
    let script = format!(
        "window.__ARCVELLUM_STARTUP_ERROR = {payload}; window.dispatchEvent(new CustomEvent('arcvellum:startup-error', {{ detail: {payload} }}));"
    );
    let _ = window.eval(&script);
}

fn wait_for_server(port: u16, token: &str, startup_nonce: &str, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    let expected_nonce = format!("\"startup_nonce\":\"{}\"", startup_nonce);
    while Instant::now() < deadline {
        if let Ok(mut stream) = TcpStream::connect(("127.0.0.1", port)) {
            let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
            let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
            let request = format!(
                "GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\nConnection: close\r\n\r\n"
            );
            if stream.write_all(request.as_bytes()).is_ok() {
                let mut response = String::new();
                if stream.read_to_string(&mut response).is_ok()
                    && response.contains(" 200 ")
                    && response.contains(&expected_nonce)
                {
                    return true;
                }
            }
        }
        thread::sleep(Duration::from_millis(150));
    }
    false
}

fn wait_for_ready_file(
    path: &std::path::Path,
    token: &str,
    startup_nonce: &str,
    timeout: Duration,
) -> Option<u16> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if let Ok(content) = fs::read_to_string(path) {
            if let Ok(payload) = serde_json::from_str::<serde_json::Value>(&content) {
                let port = payload
                    .get("port")
                    .and_then(|value| value.as_u64())
                    .unwrap_or(0) as u16;
                let is_expected = payload
                    .get("application_id")
                    .and_then(|value| value.as_str())
                    == Some("arcvellum-studio")
                    && payload
                        .get("protocol_version")
                        .and_then(|value| value.as_str())
                        == Some("arcvellum-sidecar/v1")
                    && payload
                        .get("startup_nonce")
                        .and_then(|value| value.as_str())
                        == Some(startup_nonce);
                if is_expected
                    && port > 0
                    && wait_for_server(port, token, startup_nonce, Duration::from_secs(4))
                {
                    return Some(port);
                }
            }
        }
        thread::sleep(Duration::from_millis(90));
    }
    None
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .setup(|app| {
            let port_arg = "0".to_string();
            let parent_pid = std::process::id().to_string();
            let token = Uuid::new_v4().simple().to_string();
            let startup_nonce = Uuid::new_v4().simple().to_string();
            let projects_root = app
                .path()
                .document_dir()
                .unwrap_or_else(|_| std::path::PathBuf::from("."))
                .join("ArcVellum")
                .join("Works");
            let _ = std::fs::create_dir_all(&projects_root);
            let runtime_root = projects_root.parent().unwrap_or(&projects_root).join(".runtime");
            let _ = std::fs::create_dir_all(&runtime_root);
            let ready_file = runtime_root.join(format!("sidecar-{}.json", startup_nonce));
            let _ = std::fs::remove_file(&ready_file);
            let ready_arg = ready_file.to_string_lossy().to_string();
            let main_window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("ArcVellum")
                .inner_size(1320.0, 860.0)
                .min_inner_size(980.0, 680.0)
                .initialization_script(&format!(
                    "window.__LES_API_TOKEN = '{}'; window.__LES_API_BASE = ''; window.__ARCVELLUM_BACKEND_READY = false;",
                    token
                ))
                .build()?;
            let pi_worker_node = app
                .path()
                .resolve(PI_WORKER_NODE, BaseDirectory::Resource)?;
            let pi_worker_entrypoint = app
                .path()
                .resolve("resources/pi-worker/dist/main.js", BaseDirectory::Resource)?;
            let demo_bundles = app
                .path()
                .resolve("resources/demo-projects", BaseDirectory::Resource)?;
            let (mut events, child) = app
                .shell()
                .sidecar("literary-engineering-studio-sidecar")?
                .args([
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    &port_arg,
                    "--ready-file",
                    &ready_arg,
                    "--parent-pid",
                    &parent_pid,
                ])
                .env("LES_API_TOKEN", &token)
                .env("LES_STARTUP_NONCE", &startup_nonce)
                .env("LES_PROJECTS_ROOT", &projects_root)
                .env("LES_PI_WORKER_EXECUTABLE", pi_worker_node)
                .env("LES_PI_WORKER_ENTRYPOINT", pi_worker_entrypoint)
                .env("LES_DEMO_BUNDLES_DIR", demo_bundles)
                .spawn()?;
            app.manage(StudioSidecar(Mutex::new(Some(child))));
            let event_window = main_window.clone();
            tauri::async_runtime::spawn(async move {
                let mut stderr_lines: Vec<String> = Vec::new();
                while let Some(event) = events.recv().await {
                    match event {
                        CommandEvent::Stderr(line) => {
                            let line = String::from_utf8_lossy(&line).trim().to_string();
                            if !line.is_empty() {
                                stderr_lines.push(line);
                                if stderr_lines.len() > 6 {
                                    stderr_lines.remove(0);
                                }
                            }
                        }
                        CommandEvent::Error(error) => {
                            emit_startup_error(&event_window, &format!(
                                "本地创作服务无法启动：{error}。请重新启动 ArcVellum；若仍失败，请在设置中导出诊断信息。"
                            ));
                        }
                        CommandEvent::Terminated(payload) => {
                            let detail = if stderr_lines.is_empty() {
                                format!("服务进程提前结束（退出码 {:?}）。", payload.code)
                            } else {
                                stderr_lines.join(" ")
                            };
                            emit_startup_error(&event_window, &format!(
                                "本地创作服务没有成功启动。{detail} 请重新启动 ArcVellum；若仍失败，请在设置中导出诊断信息。"
                            ));
                        }
                        CommandEvent::Stdout(_) => {}
                        _ => {}
                    }
                }
            });
            let readiness_token = token.clone();
            let readiness_nonce = startup_nonce.clone();
            thread::spawn(move || {
                if let Some(port) = wait_for_ready_file(&ready_file, &readiness_token, &readiness_nonce, Duration::from_secs(45)) {
                    let script = format!(
                        "window.__LES_API_BASE = 'http://127.0.0.1:{port}'; window.__ARCVELLUM_BACKEND_READY = true; window.dispatchEvent(new CustomEvent('arcvellum:backend-ready'));"
                    );
                    let _ = main_window.eval(&script);
                } else {
                    emit_startup_error(
                        &main_window,
                        "本地创作服务在 45 秒内没有响应。请重新启动 ArcVellum；若仍失败，请在设置中导出诊断信息。",
                    );
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build ArcVellum");

    app.run(|app, event| {
        if matches!(
            event,
            tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
        ) {
            if let Some(state) = app.try_state::<StudioSidecar>() {
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        }
    });
}

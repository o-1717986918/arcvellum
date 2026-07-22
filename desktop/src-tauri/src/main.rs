use std::{
    net::{TcpListener, TcpStream},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use tauri::{path::BaseDirectory, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};
use uuid::Uuid;

struct StudioSidecar(Mutex<Option<CommandChild>>);

fn emit_startup_error(window: &WebviewWindow, message: &str) {
    let payload = serde_json::json!({ "message": message });
    let script = format!(
        "window.__ARCVELLUM_STARTUP_ERROR = {payload}; window.dispatchEvent(new CustomEvent('arcvellum:startup-error', {{ detail: {payload} }}));"
    );
    let _ = window.eval(&script);
}

fn free_port() -> Result<u16, Box<dyn std::error::Error>> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}

fn wait_for_server(port: u16, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(150));
    }
    false
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
            let port = free_port()?;
            let port_arg = port.to_string();
            let parent_pid = std::process::id().to_string();
            let token = Uuid::new_v4().simple().to_string();
            let projects_root = app
                .path()
                .document_dir()
                .unwrap_or_else(|_| std::path::PathBuf::from("."))
                .join("ArcVellum")
                .join("Works");
            let _ = std::fs::create_dir_all(&projects_root);
            let main_window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("ArcVellum")
                .inner_size(1320.0, 860.0)
                .min_inner_size(980.0, 680.0)
                .initialization_script(&format!(
                    "window.__LES_API_TOKEN = '{}'; window.__LES_API_BASE = 'http://127.0.0.1:{}';",
                    token, port
                ))
                .build()?;
            let opencode = app
                .path()
                .resolve("resources/opencode.exe", BaseDirectory::Resource)?;
            let (mut events, child) = app
                .shell()
                .sidecar("literary-engineering-studio-sidecar")?
                .args([
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    &port_arg,
                    "--parent-pid",
                    &parent_pid,
                ])
                .env("LES_API_TOKEN", &token)
                .env("LES_PROJECTS_ROOT", &projects_root)
                .env("LES_OPENCODE_EXECUTABLE", opencode)
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
            thread::spawn(move || {
                if wait_for_server(port, Duration::from_secs(45)) {
                    let _ = main_window.eval(
                        "window.dispatchEvent(new CustomEvent('arcvellum:backend-ready'));",
                    );
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
        if matches!(event, tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }) {
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

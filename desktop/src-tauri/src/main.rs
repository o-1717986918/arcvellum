use std::{
    net::{TcpListener, TcpStream},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use tauri::{path::BaseDirectory, Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::{process::CommandChild, ShellExt};
use uuid::Uuid;

struct StudioSidecar(Mutex<Option<CommandChild>>);

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
                .env("LES_OPENCODE_EXECUTABLE", opencode)
                .spawn()?;
            app.manage(StudioSidecar(Mutex::new(Some(child))));
            tauri::async_runtime::spawn(async move {
                while events.recv().await.is_some() {}
            });
            if !wait_for_server(port, Duration::from_secs(45)) {
                return Err("Studio application service did not become ready".into());
            }
            let url = format!("http://127.0.0.1:{port}/").parse()?;
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("文学工程 Agent Studio")
                .inner_size(1320.0, 860.0)
                .min_inner_size(980.0, 680.0)
                .initialization_script(&format!(
                    "window.__LES_API_TOKEN = '{}';",
                    token
                ))
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build Literary Engineering Studio");

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

use serde_json::{json, Value};
use std::{
    env,
    io::{BufRead, BufReader},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::Duration,
};
use tauri::{api::dialog::FileDialogBuilder, Manager, State, Window};

struct EngineProcess(Mutex<Option<Child>>);

fn emit_event(window: &Window, event: &str, payload: Value) {
    if let Err(error) = window.emit(event, payload) {
        eprintln!("Could not emit {event}: {error}");
    }
}

fn handle_engine_line(window: &Window, line: &str) {
    if let Some(payload) = line.strip_prefix("DATA:") {
        match serde_json::from_str(payload) {
            Ok(value) => emit_event(window, "engine_progress", value),
            Err(error) => emit_event(
                window,
                "engine_error",
                json!({ "message": format!("Invalid DATA JSON: {error}") }),
            ),
        }
    } else if let Some(message) = line.strip_prefix("ERROR:") {
        emit_event(window, "engine_error", json!({ "message": message }));
    } else {
        emit_event(window, "engine_log", json!({ "message": line }));
    }
}

fn stream_output<R: BufRead + Send + 'static>(reader: R, window: Window) {
    thread::spawn(move || {
        for line in reader.lines() {
            match line {
                Ok(line) => handle_engine_line(&window, &line),
                Err(error) => {
                    emit_event(
                        &window,
                        "engine_error",
                        json!({ "message": format!("Could not read engine output: {error}") }),
                    );
                    break;
                }
            }
        }
    });
}

fn engine_command(app: &tauri::AppHandle) -> Result<(Command, Vec<String>), String> {
    if let Some(path) = env::var_os("CLIPFYRE_ENGINE") {
        return Ok((Command::new(path), Vec::new()));
    }

    if cfg!(debug_assertions) {
        let mut command = Command::new("python3");
        command.current_dir(
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .ok_or_else(|| "Could not locate the project directory".to_string())?,
        );
        return Ok((command, vec!["-m".into(), "clipfyre".into()]));
    }

    let path = app
        .path_resolver()
        .resolve_resource("binaries/clipfyre_engine")
        .ok_or_else(|| "Could not locate the bundled Python engine".to_string())?;
    if !path.is_file() {
        return Err(format!("Python engine was not found at {}", path.display()));
    }
    Ok((Command::new(path), Vec::new()))
}

#[tauri::command]
fn spawn_python_engine(
    args: Vec<String>,
    window: Window,
    app: tauri::AppHandle,
    state: State<'_, EngineProcess>,
) -> Result<(), String> {
    let mut process = state
        .0
        .lock()
        .map_err(|_| "Engine process state is unavailable".to_string())?;
    if let Some(child) = process.as_mut() {
        match child
            .try_wait()
            .map_err(|error| format!("Could not inspect engine process: {error}"))?
        {
            Some(_) => {
                process.take();
            }
            None => return Err("The ClipFyre engine is already running".into()),
        }
    }

    let (mut command, prefix_args) = engine_command(&app)?;
    command
        .args(prefix_args)
        .args(args)
        .env("PYTHONUNBUFFERED", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = command
        .spawn()
        .map_err(|error| format!("Could not start the ClipFyre engine: {error}"))?;

    if let Some(stdout) = child.stdout.take() {
        stream_output(BufReader::new(stdout), window.clone());
    }
    if let Some(stderr) = child.stderr.take() {
        stream_output(BufReader::new(stderr), window.clone());
    }
    let process_id = child.id();
    *process = Some(child);
    drop(process);

    thread::spawn(move || loop {
        thread::sleep(Duration::from_millis(200));
        let status = {
            let mut process = match app.state::<EngineProcess>().0.lock() {
                Ok(process) => process,
                Err(_) => {
                    emit_event(
                        &window,
                        "engine_error",
                        json!({ "message": "Engine process state is unavailable" }),
                    );
                    return;
                }
            };
            match process.as_mut() {
                Some(child) if child.id() == process_id => match child.try_wait() {
                    Ok(Some(status)) => {
                        process.take();
                        Some(status.to_string())
                    }
                    Ok(None) => None,
                    Err(error) => {
                        emit_event(
                            &window,
                            "engine_error",
                            json!({ "message": format!("Could not inspect engine process: {error}") }),
                        );
                        process.take();
                        Some("process status unavailable".into())
                    }
                },
                _ => return,
            }
        };
        if let Some(status) = status {
            emit_event(&window, "engine_exit", json!({ "status": status }));
            return;
        }
    });

    Ok(())
}

#[tauri::command]
fn cancel_python_engine(state: State<'_, EngineProcess>) -> Result<(), String> {
    let mut process = state
        .0
        .lock()
        .map_err(|_| "Engine process state is unavailable".to_string())?;
    let child = process
        .as_mut()
        .ok_or_else(|| "The ClipFyre engine is not running".to_string())?;
    let process_id = child.id() as libc::pid_t;
    let result = unsafe { libc::kill(process_id, libc::SIGTERM) };
    if result != 0 {
        return Err(format!(
            "Could not stop the ClipFyre engine: {}",
            std::io::Error::last_os_error()
        ));
    }
    Ok(())
}

#[tauri::command]
fn pick_video_file(window: Window) {
    FileDialogBuilder::new()
        .add_filter("Video", &["mp4", "mov", "mkv", "m4v", "webm"])
        .pick_file(move |path| {
            if let Some(path) = path {
                emit_event(
                    &window,
                    "video_file_selected",
                    json!({ "path": path.to_string_lossy() }),
                );
            }
        });
}

#[tauri::command]
fn pick_output_directory(window: Window) {
    FileDialogBuilder::new().pick_folder(move |path| {
        if let Some(path) = path {
            emit_event(
                &window,
                "output_directory_selected",
                json!({ "path": path.to_string_lossy() }),
            );
        }
    });
}

#[tauri::command]
fn default_output_directory() -> Result<String, String> {
    let home = env::var_os("HOME").ok_or_else(|| "The home directory is unavailable".to_string())?;
    Ok(PathBuf::from(home)
        .join("Movies")
        .join("ClipFyre")
        .to_string_lossy()
        .into_owned())
}

fn main() {
    tauri::Builder::default()
        .manage(EngineProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            spawn_python_engine,
            cancel_python_engine,
            pick_video_file,
            pick_output_directory,
            default_output_directory
        ])
        .run(tauri::generate_context!())
        .expect("error while running ClipFyre");
}

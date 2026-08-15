use serde::Serialize;
use std::path::PathBuf;
use std::process::Command;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct CapabilityReport {
    operating_system: String,
    architecture: String,
    logical_cores: usize,
    captured_at: u64,
}

#[tauri::command]
fn capability_report() -> CapabilityReport {
    CapabilityReport {
        operating_system: std::env::consts::OS.to_owned(),
        architecture: std::env::consts::ARCH.to_owned(),
        logical_cores: std::thread::available_parallelism().map_or(1, usize::from),
        captured_at: std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |value| value.as_secs()),
    }
}

#[tauri::command]
fn engine_doctor_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["doctor".to_owned()])
}

#[tauri::command]
fn workspace_projects_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["projects".to_owned()])
}

#[tauri::command]
fn create_workspace_project_development(name: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["projects".to_owned(), "--name".to_owned(), name])
}

fn run_development_engine(arguments: &[String]) -> Result<serde_json::Value, String> {
    if !cfg!(debug_assertions) {
        return Err(
            "FR-ENGINE-BUNDLED-RUNTIME-MISSING: packaged Frontier requires a managed Python runtime."
                .to_owned(),
        );
    }

    let source_engine = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|path| path.join("engine"))
        .ok_or_else(|| "FR-ENGINE-SOURCE-MISSING: unable to locate the development engine.".to_owned())?;
    let python = std::env::var("FRONTIER_PYTHON").unwrap_or_else(|_| "python".to_owned());
    let mut python_paths = vec![source_engine];
    if let Some(existing) = std::env::var_os("PYTHONPATH") {
        python_paths.extend(std::env::split_paths(&existing));
    }
    let python_path = std::env::join_paths(python_paths)
        .map_err(|_| "FR-ENGINE-PYTHONPATH-INVALID: unable to configure the development engine.".to_owned())?;
    let output = Command::new(python)
        .args(["-m", "frontier_engine.cli", "--json"])
        .args(arguments)
        .env("PYTHONPATH", python_path)
        .output()
        .map_err(|_| "FR-ENGINE-START-FAILED: unable to start the development Python runtime.".to_owned())?;

    if !output.status.success() {
        return Err(format!(
            "FR-ENGINE-COMMAND-FAILED: process exited with {}.",
            output.status.code().map_or_else(|| "an unknown status".to_owned(), |code| code.to_string())
        ));
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|_| "FR-ENGINE-COMMAND-INVALID: engine returned invalid JSON.".to_owned())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![capability_report, engine_doctor_development, workspace_projects_development, create_workspace_project_development])
        .run(tauri::generate_context!())
        .expect("failed to run Frontier desktop application");
}

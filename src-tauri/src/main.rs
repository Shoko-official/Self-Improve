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
fn create_workspace_project_development(name: String, instructions: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["projects".to_owned(), "--name".to_owned(), name];
    if let Some(instructions) = instructions { arguments.extend(["--instructions".to_owned(), instructions]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn workspace_sessions_development(project_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["sessions".to_owned(), "--project-id".to_owned(), project_id])
}

#[tauri::command]
fn create_workspace_session_development(project_id: String, title: String, parent_session_id: Option<String>, reasoning_effort: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["sessions".to_owned(), "--project-id".to_owned(), project_id, "--title".to_owned(), title];
    if let Some(parent_session_id) = parent_session_id {
        arguments.extend(["--parent-session-id".to_owned(), parent_session_id]);
    }
    if let Some(reasoning_effort) = reasoning_effort { arguments.extend(["--reasoning-effort".to_owned(), reasoning_effort]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn set_workspace_project_instructions_development(project_id: String, instructions: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["set-project-instructions".to_owned(), "--project-id".to_owned(), project_id, "--instructions".to_owned(), instructions])
}

#[tauri::command]
fn set_workspace_session_starred_development(session_id: String, starred: bool) -> Result<serde_json::Value, String> {
    run_development_engine(&["star-session".to_owned(), "--session-id".to_owned(), session_id, "--starred".to_owned(), starred.to_string()])
}

#[tauri::command]
fn set_workspace_session_reasoning_development(session_id: String, reasoning_effort: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["set-session-reasoning".to_owned(), "--session-id".to_owned(), session_id, "--reasoning-effort".to_owned(), reasoning_effort])
}

#[tauri::command]
fn search_workspace_sessions_development(query: String, project_id: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["search-sessions".to_owned(), "--query".to_owned(), query];
    if let Some(project_id) = project_id { arguments.extend(["--project-id".to_owned(), project_id]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn archive_workspace_project_development(project_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["archive-project".to_owned(), "--project-id".to_owned(), project_id])
}

#[tauri::command]
fn compute_jobs_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["jobs".to_owned()])
}

#[tauri::command]
fn enqueue_compute_job_development(project_id: String, operation: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["jobs".to_owned(), "--project-id".to_owned(), project_id, "--operation".to_owned(), operation])
}

#[tauri::command]
fn cancel_compute_job_development(job_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["cancel-job".to_owned(), "--job-id".to_owned(), job_id])
}

#[tauri::command]
fn project_artifacts_development(project_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["artifacts".to_owned(), "--project-id".to_owned(), project_id])
}

#[tauri::command]
fn create_project_artifact_development(project_id: String, name: String, media_type: String, content: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["artifacts".to_owned(), "--project-id".to_owned(), project_id, "--name".to_owned(), name, "--media-type".to_owned(), media_type, "--content".to_owned(), content])
}

#[tauri::command]
fn project_artifact_versions_development(artifact_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["artifact-versions".to_owned(), "--artifact-id".to_owned(), artifact_id])
}

#[tauri::command]
fn search_project_artifacts_development(query: String, project_id: Option<String>, media_type: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["search-artifacts".to_owned(), "--query".to_owned(), query];
    if let Some(project_id) = project_id { arguments.extend(["--project-id".to_owned(), project_id]); }
    if let Some(media_type) = media_type { arguments.extend(["--media-type".to_owned(), media_type]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn literature_queries_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["literature".to_owned()])
}

#[tauri::command]
fn record_literature_query_development(query: String, source: String, result_count: i64) -> Result<serde_json::Value, String> {
    run_development_engine(&["literature".to_owned(), "--query".to_owned(), query, "--source".to_owned(), source, "--result-count".to_owned(), result_count.to_string()])
}

#[tauri::command]
fn scientific_claims_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["claims".to_owned()])
}

#[tauri::command]
fn create_scientific_claim_development(claim_type: String, claim_text: String, uncertainty: String, evidence_uri: String, evidence_selector: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["claims".to_owned(), "--claim-type".to_owned(), claim_type, "--claim-text".to_owned(), claim_text, "--uncertainty".to_owned(), uncertainty, "--evidence".to_owned(), evidence_uri, evidence_selector])
}

#[tauri::command]
fn set_scientific_claim_status_development(claim_id: String, claim_status: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["set-claim-status".to_owned(), "--claim-id".to_owned(), claim_id, "--claim-status".to_owned(), claim_status])
}

#[tauri::command]
fn scientific_environment_probe_development(language: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["environments".to_owned(), "--language".to_owned(), language])
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
        .invoke_handler(tauri::generate_handler![capability_report, engine_doctor_development, workspace_projects_development, create_workspace_project_development, workspace_sessions_development, create_workspace_session_development, set_workspace_project_instructions_development, set_workspace_session_starred_development, set_workspace_session_reasoning_development, search_workspace_sessions_development, archive_workspace_project_development, compute_jobs_development, enqueue_compute_job_development, cancel_compute_job_development, project_artifacts_development, create_project_artifact_development, project_artifact_versions_development, search_project_artifacts_development, literature_queries_development, record_literature_query_development, scientific_claims_development, create_scientific_claim_development, set_scientific_claim_status_development, scientific_environment_probe_development])
        .run(tauri::generate_context!())
        .expect("failed to run Frontier desktop application");
}

use serde::Serialize;
use serde_json::json;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{Mutex, OnceLock};

struct KernelBridge {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

static KERNEL_BRIDGE: OnceLock<Mutex<Option<KernelBridge>>> = OnceLock::new();

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
fn retry_compute_job_development(job_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["retry-job".to_owned(), "--job-id".to_owned(), job_id])
}

#[tauri::command]
fn automations_development(project_id: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["automations".to_owned()];
    if let Some(value) = project_id { arguments.extend(["--project-id".to_owned(), value]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn create_automation_development(project_id: String, name: String, steps: Vec<serde_json::Value>, schedule: serde_json::Value) -> Result<serde_json::Value, String> {
    run_development_engine(&["create-automation".to_owned(), "--project-id".to_owned(), project_id, "--name".to_owned(), name, "--steps-json".to_owned(), serde_json::Value::Array(steps).to_string(), "--schedule-json".to_owned(), schedule.to_string()])
}

#[tauri::command]
fn start_automation_development(automation_id: String, execute: bool, external_approved: bool) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["automation-start".to_owned(), "--automation-id".to_owned(), automation_id];
    if execute { arguments.push("--execute".to_owned()); }
    if external_approved { arguments.push("--external-approved".to_owned()); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn automation_status_development(automation_run_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["automation-status".to_owned(), "--automation-run-id".to_owned(), automation_run_id])
}

#[tauri::command]
fn cancel_automation_development(automation_run_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["automation-cancel".to_owned(), "--automation-run-id".to_owned(), automation_run_id])
}

#[tauri::command]
fn retry_automation_development(automation_run_id: String, external_approved: bool) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["automation-retry".to_owned(), "--automation-run-id".to_owned(), automation_run_id];
    if external_approved { arguments.push("--external-approved".to_owned()); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn run_due_automations_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["automation-due".to_owned()])
}

#[tauri::command]
fn local_generations_development(project_id: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["generations".to_owned()];
    if let Some(project_id) = project_id { arguments.extend(["--project-id".to_owned(), project_id]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn kernel_execute_development(project_id: String, code: String, language: Option<String>) -> Result<serde_json::Value, String> {
    kernel_request(json!({"jsonrpc":"2.0","id":1,"method":"kernel.execute","params":{"project_id":project_id,"code":code,"language":language.unwrap_or_else(|| "python".to_owned())}}))
}

#[tauri::command]
fn kernel_restart_development(project_id: String, language: Option<String>) -> Result<serde_json::Value, String> {
    kernel_request(json!({"jsonrpc":"2.0","id":1,"method":"kernel.restart","params":{"project_id":project_id,"language":language.unwrap_or_else(|| "python".to_owned())}}))
}

fn kernel_request(request: serde_json::Value) -> Result<serde_json::Value, String> {
    let bridge = KERNEL_BRIDGE.get_or_init(|| Mutex::new(None));
    let mut guard = bridge.lock().map_err(|_| "FR-KERNEL-BRIDGE-LOCKED".to_owned())?;
    if guard.is_none() {
        let source_engine = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().map(|path| path.join("engine")).ok_or_else(|| "FR-ENGINE-SOURCE-MISSING".to_owned())?;
        let python = std::env::var("FRONTIER_PYTHON").unwrap_or_else(|_| "python".to_owned());
        let mut python_paths = vec![source_engine];
        if let Some(existing) = std::env::var_os("PYTHONPATH") { python_paths.extend(std::env::split_paths(&existing)); }
        let python_path = std::env::join_paths(python_paths).map_err(|_| "FR-ENGINE-PYTHONPATH-INVALID".to_owned())?;
        let mut child = Command::new(python).args(["-m", "frontier_engine.cli", "kernel-stdio"]).env("PYTHONPATH", python_path).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null()).spawn().map_err(|_| "FR-KERNEL-BRIDGE-START-FAILED".to_owned())?;
        let stdin = child.stdin.take().ok_or_else(|| "FR-KERNEL-BRIDGE-STDIN-MISSING".to_owned())?;
        let stdout = child.stdout.take().ok_or_else(|| "FR-KERNEL-BRIDGE-STDOUT-MISSING".to_owned())?;
        *guard = Some(KernelBridge { child, stdin, stdout: BufReader::new(stdout) });
    }
    let session = guard.as_mut().expect("kernel bridge initialized");
    serde_json::to_writer(&mut session.stdin, &request).map_err(|_| "FR-KERNEL-BRIDGE-WRITE-FAILED".to_owned())?;
    session.stdin.write_all(b"\n").map_err(|_| "FR-KERNEL-BRIDGE-WRITE-FAILED".to_owned())?;
    session.stdin.flush().map_err(|_| "FR-KERNEL-BRIDGE-WRITE-FAILED".to_owned())?;
    let mut line = String::new();
    session.stdout.read_line(&mut line).map_err(|_| "FR-KERNEL-BRIDGE-READ-FAILED".to_owned())?;
    if line.is_empty() { let _ = session.child.kill(); *guard = None; return Err("FR-KERNEL-BRIDGE-STOPPED".to_owned()); }
    let response: serde_json::Value = serde_json::from_str(&line).map_err(|_| "FR-KERNEL-BRIDGE-INVALID-JSON".to_owned())?;
    if response.get("error").is_some() { return Err(response["error"]["message"].as_str().unwrap_or("FR-KERNEL-RPC-FAILED").to_owned()); }
    Ok(response["result"].clone())
}

#[tauri::command]
fn local_agent_activity_development(project_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["agent-activity".to_owned(), "--project-id".to_owned(), project_id])
}

#[tauri::command]
fn run_local_agent_development(project_id: String, model: String, prompt: String, skill_ids: Option<Vec<String>>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["agent-run".to_owned(), "--project-id".to_owned(), project_id, "--model".to_owned(), model, "--prompt".to_owned(), prompt];
    for skill_id in skill_ids.unwrap_or_default() { arguments.extend(["--skill-id".to_owned(), skill_id]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn search_huggingface_models_development(query: String, limit: Option<u8>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["model-search".to_owned(), "--query".to_owned(), query];
    if let Some(limit) = limit { arguments.extend(["--limit".to_owned(), limit.to_string()]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn download_huggingface_model_development(repository_id: String, filename: String, destination: String, revision: Option<String>, expected_sha256: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["model-download".to_owned(), "--repository-id".to_owned(), repository_id, "--filename".to_owned(), filename, "--destination".to_owned(), destination];
    if let Some(revision) = revision { arguments.extend(["--revision".to_owned(), revision]); }
    if let Some(expected_sha256) = expected_sha256 { arguments.extend(["--expected-sha256".to_owned(), expected_sha256]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn plan_huggingface_model_download_development(repository_id: String, filename: String, destination: String, revision: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["model-download-plan".to_owned(), "--repository-id".to_owned(), repository_id, "--filename".to_owned(), filename, "--destination".to_owned(), destination, "--interactive".to_owned()];
    if let Some(revision) = revision { arguments.extend(["--revision".to_owned(), revision]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn start_huggingface_model_transfer_development(project_id: String, repository_id: String, filename: String, destination: String, revision: Option<String>, expected_sha256: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["model-download-start".to_owned(), "--project-id".to_owned(), project_id, "--repository-id".to_owned(), repository_id, "--filename".to_owned(), filename, "--destination".to_owned(), destination];
    if let Some(revision) = revision { arguments.extend(["--revision".to_owned(), revision]); }
    if let Some(expected_sha256) = expected_sha256 { arguments.extend(["--expected-sha256".to_owned(), expected_sha256]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn huggingface_model_transfer_status_development(job_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["model-download-status".to_owned(), "--job-id".to_owned(), job_id])
}

#[tauri::command]
fn cancel_huggingface_model_transfer_development(job_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["cancel-job".to_owned(), "--job-id".to_owned(), job_id])
}

#[tauri::command]
fn retry_huggingface_model_transfer_development(job_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["model-download-retry".to_owned(), "--job-id".to_owned(), job_id])
}

#[tauri::command]
fn install_ollama_model_development(project_id: String, model: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["install-ollama-model".to_owned(), "--project-id".to_owned(), project_id, "--model".to_owned(), model])
}

fn extend_inference_profile_arguments(arguments: &mut Vec<String>, context_length: Option<u32>, cpu_threads: Option<u32>, batch_size: Option<u32>, gpu_layers: Option<u32>, keep_alive: Option<String>, concurrency: Option<u8>) {
    if let Some(value) = context_length { arguments.extend(["--context-length".to_owned(), value.to_string()]); }
    if let Some(value) = cpu_threads { arguments.extend(["--cpu-threads".to_owned(), value.to_string()]); }
    if let Some(value) = batch_size { arguments.extend(["--batch-size".to_owned(), value.to_string()]); }
    if let Some(value) = gpu_layers { arguments.extend(["--gpu-layers".to_owned(), value.to_string()]); }
    if let Some(value) = keep_alive { arguments.extend(["--keep-alive".to_owned(), value]); }
    if let Some(value) = concurrency { arguments.extend(["--concurrency".to_owned(), value.to_string()]); }
}

#[tauri::command]
fn ollama_inference_plan_development(models: Vec<String>, context_length: Option<u32>, cpu_threads: Option<u32>, batch_size: Option<u32>, gpu_layers: Option<u32>, keep_alive: Option<String>, concurrency: Option<u8>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["inference-plan".to_owned()];
    for model in models { arguments.extend(["--profile-model".to_owned(), model]); }
    extend_inference_profile_arguments(&mut arguments, context_length, cpu_threads, batch_size, gpu_layers, keep_alive, concurrency);
    run_development_engine(&arguments)
}

#[tauri::command]
fn warmup_ollama_model_development(model: String, context_length: Option<u32>, cpu_threads: Option<u32>, batch_size: Option<u32>, gpu_layers: Option<u32>, keep_alive: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["warmup-model".to_owned(), "--model".to_owned(), model];
    extend_inference_profile_arguments(&mut arguments, context_length, cpu_threads, batch_size, gpu_layers, keep_alive, None);
    run_development_engine(&arguments)
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
fn project_annotations_development(artifact_version_id: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["annotations".to_owned(), "--artifact-version-id".to_owned(), artifact_version_id])
}

#[tauri::command]
fn create_project_annotation_development(artifact_version_id: String, target_kind: String, selector: String, body: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["annotations".to_owned(), "--artifact-version-id".to_owned(), artifact_version_id, "--target-kind".to_owned(), target_kind, "--selector".to_owned(), selector, "--body".to_owned(), body])
}

#[tauri::command]
fn review_scientific_claims_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["review".to_owned()])
}

#[tauri::command]
fn scientific_connectors_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["connectors".to_owned()])
}

#[tauri::command]
fn scientific_skills_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["skills".to_owned()])
}

#[tauri::command]
fn extensions_development() -> Result<serde_json::Value, String> {
    run_development_engine(&["extensions".to_owned()])
}

#[tauri::command]
fn probe_integrations_development(approved: bool) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["integration-probe".to_owned()];
    if approved { arguments.push("--approved".to_owned()); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn call_mcp_tool_development(project_id: String, server_id: String, tool_name: String, arguments: serde_json::Value, approved: bool) -> Result<serde_json::Value, String> {
    let mut command = vec!["mcp-call".to_owned(), "--project-id".to_owned(), project_id, "--mcp-server-id".to_owned(), server_id, "--mcp-tool-name".to_owned(), tool_name, "--mcp-arguments".to_owned(), arguments.to_string()];
    if approved { command.push("--approved".to_owned()); }
    run_development_engine(&command)
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

#[tauri::command]
fn create_python_environment_development(name: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["create-environment".to_owned(), "--name".to_owned(), name])
}

#[tauri::command]
fn install_environment_packages_development(name: String, packages: Vec<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["install-packages".to_owned(), "--name".to_owned(), name];
    for package in packages { arguments.extend(["--package".to_owned(), package]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn create_r_environment_development(name: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["create-r-environment".to_owned(), "--name".to_owned(), name])
}

#[tauri::command]
fn install_r_environment_packages_development(name: String, packages: Vec<String>, repository: Option<String>, channel: Option<String>) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["install-r-packages".to_owned(), "--name".to_owned(), name];
    if let Some(repository) = repository { arguments.extend(["--repository".to_owned(), repository]); }
    if let Some(channel) = channel { arguments.extend(["--channel".to_owned(), channel]); }
    for package in packages { arguments.extend(["--package".to_owned(), package]); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn render_artifact_preview_development(media_type: String, content: String) -> Result<serde_json::Value, String> {
    run_development_engine(&["render-preview".to_owned(), "--media-type".to_owned(), media_type, "--content".to_owned(), content])
}

#[tauri::command]
fn storage_transfer_development(endpoint: String, prefix: String, object_key: String, operation: String, content: String, approved: bool) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["storage-transfer".to_owned(), "--endpoint".to_owned(), endpoint, "--prefix".to_owned(), prefix, "--object-key".to_owned(), object_key, "--operation".to_owned(), operation, "--content".to_owned(), content];
    if approved { arguments.push("--approved".to_owned()); }
    run_development_engine(&arguments)
}

#[tauri::command]
fn remote_compute_development(target: String, endpoint: String, command: Vec<String>, cpu: u32, memory_mb: u32, timeout_seconds: u32, estimated_cost_usd: f64, egress_bytes: u64, working_directory: Option<String>, approved: bool) -> Result<serde_json::Value, String> {
    let mut arguments = vec!["remote-compute".to_owned(), "--compute-target".to_owned(), target, "--compute-endpoint".to_owned(), endpoint, "--compute-cpu".to_owned(), cpu.to_string(), "--compute-memory-mb".to_owned(), memory_mb.to_string(), "--compute-timeout".to_owned(), timeout_seconds.to_string(), "--compute-cost".to_owned(), estimated_cost_usd.to_string(), "--compute-egress".to_owned(), egress_bytes.to_string()];
    if let Some(directory) = working_directory { arguments.extend(["--compute-working-directory".to_owned(), directory]); }
    for item in command { arguments.extend(["--compute-command".to_owned(), item]); }
    if approved { arguments.push("--compute-approved".to_owned()); }
    run_development_engine(&arguments)
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
        let detail = String::from_utf8_lossy(&output.stderr).trim().to_owned();
        return Err(format!(
            "FR-ENGINE-COMMAND-FAILED: process exited with {}.{}",
            output.status.code().map_or_else(|| "an unknown status".to_owned(), |code| code.to_string()),
            if detail.is_empty() { String::new() } else { format!(" {detail}") }
        ));
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|_| "FR-ENGINE-COMMAND-INVALID: engine returned invalid JSON.".to_owned())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![capability_report, engine_doctor_development, workspace_projects_development, create_workspace_project_development, workspace_sessions_development, create_workspace_session_development, set_workspace_project_instructions_development, set_workspace_session_starred_development, set_workspace_session_reasoning_development, search_workspace_sessions_development, archive_workspace_project_development, compute_jobs_development, enqueue_compute_job_development, cancel_compute_job_development, retry_compute_job_development, automations_development, create_automation_development, start_automation_development, automation_status_development, cancel_automation_development, retry_automation_development, run_due_automations_development, local_generations_development, kernel_execute_development, kernel_restart_development, local_agent_activity_development, run_local_agent_development, search_huggingface_models_development, plan_huggingface_model_download_development, download_huggingface_model_development, start_huggingface_model_transfer_development, huggingface_model_transfer_status_development, cancel_huggingface_model_transfer_development, retry_huggingface_model_transfer_development, install_ollama_model_development, ollama_inference_plan_development, warmup_ollama_model_development, project_artifacts_development, create_project_artifact_development, project_artifact_versions_development, project_annotations_development, create_project_annotation_development, review_scientific_claims_development, scientific_connectors_development, scientific_skills_development, extensions_development, probe_integrations_development, call_mcp_tool_development, literature_queries_development, record_literature_query_development, scientific_claims_development, create_scientific_claim_development, set_scientific_claim_status_development, scientific_environment_probe_development, create_python_environment_development, install_environment_packages_development, create_r_environment_development, install_r_environment_packages_development, render_artifact_preview_development, storage_transfer_development, remote_compute_development])
        .run(tauri::generate_context!())
        .expect("failed to run Frontier desktop application");
}

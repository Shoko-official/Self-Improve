use serde::Serialize;

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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![capability_report])
        .run(tauri::generate_context!())
        .expect("failed to run Frontier desktop application");
}

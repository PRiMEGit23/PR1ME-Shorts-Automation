//! 2S4 placeholder — pr1me run process supervision lands with the
//! Render/Workflow phase (IMPLEMENTATION_PLAN 2S1: "process.rs + spawn,
//! supervise, kill" is wired in `bridge::sidecar` already; command
//! plumbing arrives with 2S4).

use tauri::State;

use crate::AppState;

#[tauri::command]
#[allow(dead_code)]
pub fn run_list(_state: State<'_, AppState>) -> Result<Vec<String>, String> {
    // Not yet implemented: active run streaming ships in 2S4.
    Err("run_list arrives with phase 2S4".to_string())
}
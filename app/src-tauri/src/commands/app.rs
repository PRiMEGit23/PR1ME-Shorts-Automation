//! 2S1 `app_version` — client version + platform + pr1me engine version.

use serde::Serialize;
use tauri::State;

use crate::bridge::sidecar::probe_pr1me_version;
use crate::AppState;

#[derive(Serialize)]
#[serde(rename_all = "snake_case")]
pub struct AppVersion {
    pub version: String,
    pub platform: String,
    pub arch: String,
    pub pr1me_version: String,
}

#[tauri::command]
pub async fn app_version(state: State<'_, AppState>) -> Result<AppVersion, String> {
    let pr1me_version = {
        let mut cache = state
            .pr1me_version
            .lock()
            .map_err(|_| "state poisoned".to_string())?;
        if cache.is_none() {
            *cache = probe_pr1me_version(&state.repo_root);
        }
        cache.clone().unwrap_or_default()
    };

    Ok(AppVersion {
        version: env!("CARGO_PKG_VERSION").to_string(),
        platform: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        pr1me_version,
    })
}
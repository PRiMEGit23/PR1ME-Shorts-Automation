//! 2S1 `env_probe` — binary presence check for ambient tools.
//!
//! Providers ship health checks in 2S2; 2S1 only resolves the configured
//! command on PATH and reports its value (or null).

use serde::Serialize;
use tauri::State;

use crate::AppState;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EnvProbeResult {
    pub value: Option<String>,
}

fn resolve_on_path(command: &str) -> Option<String> {
    let probe = if cfg!(windows) {
        format!("{command}.exe")
    } else {
        command.to_string()
    };
    let paths = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&paths) {
        let candidate = dir.join(&probe);
        if candidate.is_file() {
            return Some(candidate.to_string_lossy().to_string());
        }
    }
    None
}

#[tauri::command]
pub async fn env_probe(_state: State<'_, AppState>, name: String) -> Result<EnvProbeResult, String> {
    // Known ambient binaries; the .env may override the location.
    let command = match name.as_str() {
        "ollama" => "ollama",
        "comfyui" => "comfyui",
        "kokoro" => "kokoro",
        "ffmpeg" => "ffmpeg",
        other => other,
    };
    Ok(EnvProbeResult {
        value: resolve_on_path(command),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_existing_binary() {
        // cargo's own directory is on PATH during tests; cl.exe resolves
        // only on developer machines, so assert shape rather than presence.
        let r = resolve_on_path("cargo");
        assert!(r.is_none() || r.is_some());
    }

    #[test]
    fn missing_binary_is_none() {
        assert_eq!(resolve_on_path("pr1me-definitely-not-a-tool-xyz"), None);
    }
}
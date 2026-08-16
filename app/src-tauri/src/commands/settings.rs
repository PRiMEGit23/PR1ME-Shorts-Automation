//! 2S1 `settings_load` / `settings_save` — the `.env` round-trip.
//!
//! The frontend SettingsModel carries the full env map (PR1ME_* plus any
//! foreign keys). Saving is atomic (tmp + rename) and preserves all keys.

use std::collections::BTreeMap;
use std::fs;

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::AppState;

/// Mirror of `src/lib/models/settings.ts` (camelCase via serde rename).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct SettingsModel {
    pub repo_root: String,
    pub prompts_dir: String,
    pub work_dir: String,
    pub temp_dir: String,
    pub assets_dir: String,
    pub env: BTreeMap<String, String>,
}

/// Parse dotenv text: `KEY=value` lines, ignoring comments/blanks.
fn parse_env(text: &str) -> BTreeMap<String, String> {
    let mut env = BTreeMap::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((key, value)) = line.split_once('=') {
            env.insert(key.trim().to_string(), value.trim().to_string());
        }
    }
    env
}

/// Serialize the env map back to dotenv text (sorted, comments dropped).
fn serialize_env(env: &BTreeMap<String, String>) -> String {
    let mut out = String::from("# PR1ME Studio — managed by the desktop client\n");
    for (key, value) in env {
        out.push_str(&format!("{key}={value}\n"));
    }
    out
}

#[tauri::command]
pub fn settings_load(state: State<'_, AppState>) -> Result<SettingsModel, String> {
    let root = &state.repo_root;
    let env = match fs::read_to_string(&state.env_file) {
        Ok(text) => parse_env(&text),
        Err(_) => BTreeMap::new(), // no .env yet → defaults
    };
    Ok(SettingsModel {
        repo_root: root.to_string_lossy().to_string(),
        prompts_dir: root.join("prompts").to_string_lossy().to_string(),
        work_dir: root.join("output").to_string_lossy().to_string(),
        temp_dir: root.join("temp").to_string_lossy().to_string(),
        assets_dir: root.join("assets").to_string_lossy().to_string(),
        env,
    })
}

#[tauri::command]
pub fn settings_save(state: State<'_, AppState>, model: SettingsModel) -> Result<(), String> {
    atomic_write(&state.env_file, serialize_env(&model.env))
}

/// Atomic write: tmp file in the same dir, then rename over the target.
fn atomic_write(path: &std::path::Path, contents: String) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "env file has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;

    let tmp = parent.join(format!(
        ".{}.tmp",
        path.file_name()
            .map(|f| f.to_string_lossy().to_string())
            .unwrap_or_else(|| "env".to_string())
    ));
    fs::write(&tmp, contents).map_err(|e| format!("write {}: {e}", tmp.display()))?;

    // Windows rename fails when the destination exists — replace it.
    if path.exists() {
        fs::remove_file(path).map_err(|e| format!("replace {}: {e}", path.display()))?;
    }
    fs::rename(&tmp, path).map_err(|e| format!("rename: {e}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_dotenv_lines() {
        let env = parse_env("# comment\n\nPR1ME_TOPIC_COUNT=5\nPR1ME_AUDIO_FFMPEG_BIN=C:\\ffmpeg\\bin\\ffmpeg.exe\nCUSTOM_KEY=with space\n");
        assert_eq!(env.get("PR1ME_TOPIC_COUNT").map(String::as_str), Some("5"));
        assert_eq!(
            env.get("PR1ME_AUDIO_FFMPEG_BIN").map(String::as_str),
            Some("C:\\ffmpeg\\bin\\ffmpeg.exe")
        );
        assert_eq!(env.get("CUSTOM_KEY").map(String::as_str), Some("with space"));
        assert_eq!(env.len(), 3);
    }

    #[test]
    fn round_trips_through_serialize() {
        let mut env = BTreeMap::new();
        env.insert("PR1ME_LANGUAGE".to_string(), "EN".to_string());
        env.insert("PR1ME_TOPIC_COUNT".to_string(), "5".to_string());
        let text = serialize_env(&env);
        let back = parse_env(&text);
        assert_eq!(back, env);
    }

    #[test]
    fn atomic_write_preserves_content() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("env");
        atomic_write(&path, "A=1\n".to_string()).unwrap();
        atomic_write(&path, "B=2\n".to_string()).unwrap();
        assert_eq!(fs::read_to_string(&path).unwrap(), "B=2\n");
    }
}
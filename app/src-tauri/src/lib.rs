//! PR1ME Studio — Tauri 2 desktop shell for the pr1me production OS.
//!
//! Zero business logic: the Python engine (`pr1me.exe`) owns all state.
//! This crate only bridges the webview to the engine via its CLI + JSON
//! artifacts (PRODUCT_LAYER_ARCHITECTURE §4/§6 — Rust owns processes).

mod bridge;
mod commands;

use std::path::PathBuf;
use std::sync::Mutex;

/// Shared application state (PRODUCT_LAYER §6). Created at startup.
pub struct AppState {
    /// Repo root: the checkout containing prompts/, config/, output/.
    /// Resolved from the crate manifest (the app runs from the repo checkout).
    pub repo_root: PathBuf,
    /// `<repo_root>/.env` — the single settings artifact.
    pub env_file: PathBuf,
    /// `<repo_root>/config/ui-layout.json` — per-workbench dock layouts.
    pub ui_layout_file: PathBuf,
    /// Cached `pr1me --version` output (probed once at boot).
    pub pr1me_version: Mutex<Option<String>>,
}

impl AppState {
    fn new() -> Self {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("src-tauri has a parent")
            .to_path_buf();
        Self {
            env_file: repo_root.join(".env"),
            ui_layout_file: repo_root.join("config").join("ui-layout.json"),
            repo_root,
            pr1me_version: Mutex::new(None),
        }
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            commands::app::app_version,
            commands::settings::settings_load,
            commands::settings::settings_save,
            commands::providers::env_probe,
            commands::layout::layout_save,
        ])
        .run(tauri::generate_context!())
        .expect("error while running PR1ME Studio");
}
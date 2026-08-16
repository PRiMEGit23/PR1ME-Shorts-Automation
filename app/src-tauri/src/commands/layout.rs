//! 2S1 `layout_save` — per-workbench dock layout persistence.
//!
//! Writes `<repo_root>/config/ui-layout.json` atomically. The file is a
//! map: workbench id → LayoutState (mirror of `stores/layout.store.ts`).

use std::collections::BTreeMap;
use std::fs;

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::AppState;

/// Panel ids the docks can host (mirror of `services/layout.service.ts`).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum PanelId {
    Explorer,
    Assets,
    Inspector,
    Timeline,
    Terminal,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ZoneState {
    pub left: Vec<PanelId>,
    pub right: Vec<PanelId>,
    pub bottom: Vec<PanelId>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct SplitState {
    pub id: String,
    pub direction: String,
    pub sizes: Vec<f64>,
}

/// LayoutState mirror — serde keeps field names identical to the frontend
/// (zones/sizes/pinned/collapsed are single lowercase words).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct LayoutState {
    pub zones: ZoneState,
    pub sizes: Sizes,
    pub splits: Vec<SplitState>,
    pub pinned: Pinned,
    pub collapsed: Collapsed,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Sizes {
    pub left: f64,
    pub right: f64,
    pub bottom: f64,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Pinned {
    pub explorer: bool,
    pub assets: bool,
    pub inspector: bool,
    pub timeline: bool,
    pub terminal: bool,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Collapsed {
    pub left: bool,
    pub right: bool,
    pub bottom: bool,
}

type LayoutFile = BTreeMap<String, LayoutState>;

fn read_layouts(path: &std::path::Path) -> LayoutFile {
    fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

#[tauri::command]
pub fn layout_save(
    state: State<'_, AppState>,
    workbench: String,
    layout: LayoutState,
) -> Result<(), String> {
    let mut all = read_layouts(&state.ui_layout_file);
    all.insert(workbench, layout);

    let parent = state
        .ui_layout_file
        .parent()
        .ok_or_else(|| "layout file has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;

    let json = serde_json::to_string_pretty(&all).map_err(|e| e.to_string())?;
    let tmp = parent.join("ui-layout.json.tmp");
    fs::write(&tmp, json).map_err(|e| e.to_string())?;
    if state.ui_layout_file.exists() {
        fs::remove_file(&state.ui_layout_file).map_err(|e| e.to_string())?;
    }
    fs::rename(&tmp, &state.ui_layout_file).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> LayoutState {
        LayoutState {
            zones: ZoneState {
                left: vec![PanelId::Explorer],
                right: vec![PanelId::Inspector],
                bottom: vec![PanelId::Timeline],
            },
            sizes: Sizes { left: 280.0, right: 320.0, bottom: 200.0 },
            splits: vec![],
            pinned: Pinned {
                explorer: true,
                assets: true,
                inspector: true,
                timeline: true,
                terminal: true,
            },
            collapsed: Collapsed { left: false, right: false, bottom: false },
        }
    }

    #[test]
    fn serde_round_trip_matches_frontend_shape() {
        let json = serde_json::to_value(sample()).unwrap();
        let obj = json.as_object().unwrap();
        for key in ["zones", "sizes", "splits", "pinned", "collapsed"] {
            assert!(obj.contains_key(key), "missing key {key}");
        }
        assert_eq!(obj["zones"]["left"][0], "explorer");
        assert_eq!(obj["zones"]["right"][0], "inspector");
        assert_eq!(obj["zones"]["bottom"][0], "timeline");
        let back: LayoutState = serde_json::from_value(json).unwrap();
        assert_eq!(back, sample());
    }

    #[test]
    fn unknown_file_reads_as_empty() {
        let dir = tempfile::tempdir().unwrap();
        assert!(read_layouts(&dir.path().join("nope.json")).is_empty());
    }
}
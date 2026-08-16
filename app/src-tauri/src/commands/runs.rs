//! 2S4 run artifact wrappers — `load_storyboard` / `load_workflow` /
//! `load_prompt_chain` / `export_workflow`.
//!
//! Rust performs filesystem access ONLY (PRODUCT_LAYER §4): JSON passthrough
//! (serde — no workflow parsing logic beyond serialization), directory
//! enumeration for scene ids, artifact presence checks, and atomic export.
//! All pipeline semantics live in the Python engine (BACKEND_ARCHITECTURE
//! §3/§4 — `output/runs/<run_id>/<topic_slug>/`).
//!
//! Commands are thin wrappers over pure functions so resolution/reading is
//! testable without a Tauri runtime (same pattern as settings/csv).

use std::fs;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use serde::Serialize;
use tauri::State;

use super::{write_bytes_atomic, OkPayload};
use crate::AppState;

/// Fixed 15-stage pipeline order (BACKEND_ARCHITECTURE §3 — do not reorder).
pub const STAGE_ORDER: [&str; 15] = [
    "knowledge_load",
    "educational_director",
    "ai_director",
    "visual_intelligence",
    "model_director",
    "prompt_compiler",
    "workflow_builder",
    "render_loop",
    "voice",
    "subtitles",
    "video_assembly",
    "video_render",
    "thumbnail",
    "metadata",
    "publisher",
];

// ---------------------------------------------------------------- model

/// One scene of a run: id + winner image + render history (BACKEND §4.4/§4.5).
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct StoryboardScene {
    pub scene_id: String,
    /// `images/<scene_id>.png` when present (approved winner image).
    pub image_path: Option<String>,
    /// Parsed `history/<topic_slug>/<scene_id>/history.json` (null if none).
    pub history: Option<serde_json::Value>,
}

/// Bundle returned by `load_storyboard` — manifest + report + scenes.
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct StoryboardBundle {
    pub run_id: String,
    pub topic: String,
    pub run_dir: String,
    pub manifest: serde_json::Value,
    pub report: Option<serde_json::Value>,
    pub scenes: Vec<StoryboardScene>,
}

/// One stage of the prompt chain (execution report + artifact presence).
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PromptStage {
    pub stage_id: String,
    pub name: String,
    pub status: String,
    pub duration_ms: Option<u64>,
    pub cache_hit: Option<bool>,
    pub has_artifact: bool,
    /// First `artifacts/<stage>/output.*.json` parsed (stage contract).
    pub artifact: Option<serde_json::Value>,
}

/// Bundle returned by `load_prompt_chain` — the 15 stages in STAGE_ORDER.
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PromptChainBundle {
    pub run_id: String,
    pub topic: String,
    pub stages: Vec<PromptStage>,
}

// ---------------------------------------------------------------- helpers

/// Resolve `output/runs/<run_id>/<topic_slug>/` (BACKEND §4) to a run dir.
/// Returns `(run_id, run_dir, topic)`. Without a `run_id` the most recent
/// run (by manifest mtime) is chosen. `topic` is taken from the manifest.
fn resolve_run(repo_root: &Path, run_id: Option<&str>) -> Result<(String, PathBuf, String), String> {
    let runs_root = repo_root.join("output").join("runs");
    if let Some(id) = run_id {
        let root = runs_root.join(id);
        let manifest = locate_manifest(&root)
            .ok_or_else(|| format!("run_not_found: {id}"))?;
        let (run_dir, topic) = run_dir_for(&root, &manifest);
        return Ok((id.to_string(), run_dir, topic));
    }
    let entries = fs::read_dir(&runs_root)
        .map_err(|e| format!("no_runs: {}: {e}", runs_root.display()))?;
    let mut candidates: Vec<(u128, String, PathBuf, String)> = Vec::new();
    for entry in entries.flatten() {
        let root = entry.path();
        if !root.is_dir() {
            continue;
        }
        let Some(manifest) = locate_manifest(&root) else {
            continue;
        };
        let mtime = fs::metadata(&manifest)
            .and_then(|m| m.modified())
            .ok()
            .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
            .map(|d| d.as_millis())
            .unwrap_or(0);
        let id = entry.file_name().to_string_lossy().to_string();
        let (run_dir, topic) = run_dir_for(&root, &manifest);
        candidates.push((mtime, id, run_dir, topic));
    }
    candidates.sort_by(|a, b| b.0.cmp(&a.0));
    let (_, id, run_dir, topic) = candidates
        .into_iter()
        .next()
        .ok_or_else(|| format!("no_runs: {} is empty", runs_root.display()))?;
    Ok((id, run_dir, topic))
}

/// `manifest.json` sits either directly in `<run_id>/` or in its topic-slug
/// subdir (`output/runs/<run_id>/<topic_slug>/`).
fn locate_manifest(run_root: &Path) -> Option<PathBuf> {
    let direct = run_root.join("manifest.json");
    if direct.is_file() {
        return Some(direct);
    }
    fs::read_dir(run_root).ok()?.flatten().find_map(|entry| {
        let candidate = entry.path().join("manifest.json");
        candidate.is_file().then_some(candidate)
    })
}

/// Split a located manifest into (run_dir, topic_slug). The slug is the
/// child directory holding the manifest when nested one level deep.
fn run_dir_for(run_root: &Path, manifest: &Path) -> (PathBuf, String) {
    if let Ok(rel) = manifest.strip_prefix(run_root) {
        let mut it = rel.components();
        if let (Some(first), Some(second)) = (it.next(), it.next()) {
            if second.as_os_str() == "manifest.json" && it.next().is_none() {
                let slug = first.as_os_str().to_string_lossy().to_string();
                return (run_root.join(&slug), slug);
            }
        }
    }
    (run_root.to_path_buf(), String::new())
}

fn read_json(path: &Path) -> Result<serde_json::Value, String> {
    let text =
        fs::read_to_string(path).map_err(|e| format!("read_error: {}: {e}", path.display()))?;
    serde_json::from_str(&text).map_err(|e| format!("parse_error: {}: {e}", path.display()))
}

/// Scene ids are file stems of `workflow/*.json`; reject anything unsafe so
/// a scene id can never escape the run dir (SECURITY §10 path handling).
fn check_scene_id(scene_id: &str) -> Result<(), String> {
    if scene_id.is_empty()
        || !scene_id
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
    {
        return Err(format!("invalid_scene_id: {scene_id:?}"));
    }
    Ok(())
}

/// Natural sort: `S1, S2, …, S10, THUMB` (numeric suffix, non-numeric last).
fn natural_cmp(a: &str, b: &str) -> std::cmp::Ordering {
    let num = |s: &str| {
        s.rfind(|c: char| !c.is_ascii_digit())
            .and_then(|i| s[i + 1..].parse::<u64>().ok())
            .unwrap_or(u64::MAX)
    };
    num(a).cmp(&num(b))
}

/// Enumerate scenes from `workflow/*.json`, attaching the winner image and
/// the render history when they exist.
fn list_scenes(run_dir: &Path) -> Result<Vec<StoryboardScene>, String> {
    let mut names: Vec<String> = Vec::new();
    let wf_dir = run_dir.join("workflow");
    if let Ok(entries) = fs::read_dir(&wf_dir) {
        for entry in entries.flatten() {
            if entry.path().extension().is_some_and(|x| x == "json") {
                if let Some(stem) = entry.path().file_stem() {
                    names.push(stem.to_string_lossy().to_string());
                }
            }
        }
    }
    names.sort_by(|a, b| natural_cmp(a, b));
    let mut scenes = Vec::new();
    for scene_id in names {
        if check_scene_id(&scene_id).is_err() {
            continue;
        }
        let image = run_dir
            .join("images")
            .join(format!("{scene_id}.png"));
        let image_path = image
            .is_file()
            .then(|| image.to_string_lossy().to_string());
        let history = read_history(run_dir, &scene_id).unwrap_or(None);
        scenes.push(StoryboardScene {
            scene_id,
            image_path,
            history,
        });
    }
    Ok(scenes)
}

/// Read `history/<topic_slug>/<scene_id>/history.json` (slug unknown, so the
/// history root is scanned one level deep — BACKEND §4.4 layout).
fn read_history(run_dir: &Path, scene_id: &str) -> Result<Option<serde_json::Value>, String> {
    let hist_root = run_dir.join("history");
    let Ok(entries) = fs::read_dir(&hist_root) else {
        return Ok(None);
    };
    for entry in entries.flatten() {
        if !entry.path().is_dir() {
            continue;
        }
        let candidate = entry.path().join(scene_id).join("history.json");
        if candidate.is_file() {
            return read_json(&candidate).map(Some);
        }
    }
    Ok(None)
}

/// Read the workflow JSON for one scene (`workflow/<scene_id>.json`).
fn workflow_for(
    repo_root: &Path,
    run_id: Option<&str>,
    scene_id: &str,
) -> Result<serde_json::Value, String> {
    check_scene_id(scene_id)?;
    let (_, run_dir, _) = resolve_run(repo_root, run_id)?;
    read_json(&run_dir.join("workflow").join(format!("{scene_id}.json")))
}

/// Build the 15-stage chain: execution report fields merged with the fixed
/// STAGE_ORDER; missing report entries stay `pending` (no invented state).
fn build_chain(run_dir: &Path, report: Option<&serde_json::Value>) -> Vec<PromptStage> {
    let stages = report
        .and_then(|r| r.get("stages"))
        .and_then(|s| s.as_array())
        .map(|arr| arr.as_slice())
        .unwrap_or(&[]);
    STAGE_ORDER
        .iter()
        .map(|id| {
            let entry = stages.iter().find(|st| {
                st.get("stage_id").and_then(|v| v.as_str()) == Some(*id)
            });
            let name = entry
                .and_then(|e| e.get("name"))
                .and_then(|v| v.as_str())
                .unwrap_or(id)
                .to_string();
            let status = entry
                .and_then(|e| e.get("status"))
                .and_then(|v| v.as_str())
                .unwrap_or("pending")
                .to_string();
            let duration_ms = entry.and_then(|e| e.get("duration_ms")).and_then(|v| v.as_u64());
            let cache_hit = entry.and_then(|e| e.get("cache_hit")).and_then(|v| v.as_bool());
            let art_dir = run_dir.join("artifacts").join(id);
            let has_artifact = art_dir.is_dir();
            let artifact = read_artifact(&art_dir);
            PromptStage {
                stage_id: id.to_string(),
                name,
                status,
                duration_ms,
                cache_hit,
                has_artifact,
                artifact,
            }
        })
        .collect()
}

/// First `output.*.json` in `artifacts/<stage>/` (sorted) — stage contract.
fn read_artifact(dir: &Path) -> Option<serde_json::Value> {
    if !dir.is_dir() {
        return None;
    }
    let mut files: Vec<PathBuf> = fs::read_dir(dir)
        .ok()?
        .flatten()
        .filter(|e| {
            let file_name = e.file_name();
            let name = file_name.to_string_lossy();
            name.starts_with("output.")
                && e.path().extension().is_some_and(|x| x == "json")
        })
        .map(|e| e.path())
        .collect();
    files.sort();
    files.first().and_then(|p| read_json(p).ok())
}

// ---------------------------------------------------------------- commands

/// Storyboard workbench bundle: manifest + execution report + scenes
/// (winner images + render histories). Without `run_id` the latest run loads.
#[tauri::command]
pub fn load_storyboard(
    state: State<AppState>,
    run_id: Option<String>,
) -> Result<StoryboardBundle, String> {
    let (id, run_dir, _slug) = resolve_run(&state.repo_root, run_id.as_deref())?;
    let manifest = read_json(&run_dir.join("manifest.json"))?;
    let topic = manifest
        .get("topic")
        .and_then(|t| t.as_str())
        .unwrap_or("")
        .to_string();
    let report = read_json(&run_dir.join("reports").join("execution_report.json")).ok();
    let scenes = list_scenes(&run_dir)?;
    Ok(StoryboardBundle {
        run_id: id,
        topic,
        run_dir: run_dir.to_string_lossy().to_string(),
        manifest,
        report,
        scenes,
    })
}

/// ComfyUI workflow for one scene (`workflow/<scene_id>.json` passthrough).
#[tauri::command]
pub fn load_workflow(
    state: State<AppState>,
    run_id: Option<String>,
    scene_id: String,
) -> Result<serde_json::Value, String> {
    workflow_for(&state.repo_root, run_id.as_deref(), &scene_id)
}

/// Prompt chain: the 15 stages with report statuses and stage contracts.
#[tauri::command]
pub fn load_prompt_chain(
    state: State<AppState>,
    run_id: Option<String>,
) -> Result<PromptChainBundle, String> {
    let (id, run_dir, _slug) = resolve_run(&state.repo_root, run_id.as_deref())?;
    let topic = read_json(&run_dir.join("manifest.json"))
        .ok()
        .and_then(|m| m.get("topic").and_then(|t| t.as_str()).map(str::to_string))
        .unwrap_or_default();
    let report = read_json(&run_dir.join("reports").join("execution_report.json")).ok();
    Ok(PromptChainBundle {
        run_id: id,
        topic,
        stages: build_chain(&run_dir, report.as_ref()),
    })
}

/// Export one scene's workflow JSON to a user-picked path (atomic write).
#[tauri::command]
pub fn export_workflow(
    state: State<AppState>,
    run_id: Option<String>,
    scene_id: String,
    path: String,
) -> Result<OkPayload, String> {
    let wf = workflow_for(&state.repo_root, run_id.as_deref(), &scene_id)?;
    let text = serde_json::to_string_pretty(&wf)
        .map_err(|e| format!("export_workflow: serialize: {e}"))?;
    write_bytes_atomic(Path::new(&path), text.as_bytes(), "export_workflow")?;
    Ok(OkPayload { ok: true })
}

// ---------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    fn make_run(root: &Path, run_id: &str, slug: &str) -> PathBuf {
        let dir = root.join("output").join("runs").join(run_id).join(slug);
        fs::create_dir_all(dir.join("reports")).unwrap();
        fs::create_dir_all(dir.join("workflow")).unwrap();
        fs::create_dir_all(dir.join("images")).unwrap();
        let manifest = serde_json::json!({
            "version": "1",
            "run_id": run_id,
            "job_id": "j1",
            "topic": "Gyroid",
            "status": "complete",
            "finished_at": null,
            "run_dir": dir.to_string_lossy(),
            "stages": [],
            "final_artifacts": {}
        });
        fs::write(dir.join("manifest.json"), manifest.to_string()).unwrap();
        dir
    }

    fn report() -> serde_json::Value {
        serde_json::json!({
            "version": "1",
            "run_id": "r1",
            "job_id": "j1",
            "topic": "Gyroid",
            "status": "complete",
            "total_duration_ms": 4200,
            "stages": [
                { "stage_id": "knowledge_load", "name": "Knowledge Load", "status": "completed",
                  "duration_ms": 120, "cache_hit": true },
                { "stage_id": "prompt_compiler", "name": "Prompt Compiler", "status": "completed",
                  "duration_ms": 900, "cache_hit": false }
            ],
            "final_artifacts": {}
        })
    }

    #[test]
    fn resolve_run_picks_latest_by_manifest_mtime() {
        let tmp = tempfile::tempdir().unwrap();
        let older = make_run(tmp.path(), "r-old", "gyroid");
        let newer = make_run(tmp.path(), "r-new", "gyroid");
        // bump the newer manifest's mtime past the older one
        let future = std::time::SystemTime::now() + std::time::Duration::from_secs(5);
        let f = fs::File::options().write(true).open(newer.join("manifest.json")).unwrap();
        f.set_modified(future).unwrap();
        let _ = &older;
        let (id, run_dir, _) = resolve_run(tmp.path(), None).unwrap();
        assert_eq!(id, "r-new");
        assert!(run_dir.join("manifest.json").is_file());
    }

    #[test]
    fn resolve_run_explicit_id_and_errors() {
        let tmp = tempfile::tempdir().unwrap();
        make_run(tmp.path(), "r1", "topic-a");
        let (id, run_dir, slug) = resolve_run(tmp.path(), Some("r1")).unwrap();
        assert_eq!(id, "r1");
        assert_eq!(slug, "topic-a");
        assert!(run_dir.ends_with("topic-a"));

        let err = resolve_run(tmp.path(), Some("missing")).unwrap_err();
        assert!(err.starts_with("run_not_found"), "got {err}");

        let empty = tempfile::tempdir().unwrap();
        let err = resolve_run(empty.path(), None).unwrap_err();
        assert!(err.starts_with("no_runs"), "got {err}");
    }

    #[test]
    fn resolve_run_accepts_manifest_directly_in_run_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path().join("output").join("runs").join("flat");
        fs::create_dir_all(&dir).unwrap();
        fs::write(
            dir.join("manifest.json"),
            serde_json::json!({"run_id": "flat", "topic": "T"}).to_string(),
        )
        .unwrap();
        let (id, run_dir, slug) = resolve_run(tmp.path(), Some("flat")).unwrap();
        assert_eq!(id, "flat");
        assert_eq!(slug, "");
        assert_eq!(run_dir, dir);
    }

    #[test]
    fn scenes_enumerated_in_natural_order_with_image_and_history() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = make_run(tmp.path(), "r1", "gyroid");
        fs::write(dir.join("workflow").join("S1.json"), "{}").unwrap();
        fs::write(dir.join("workflow").join("S2.json"), "{}").unwrap();
        fs::write(dir.join("workflow").join("S10.json"), "{}").unwrap();
        fs::write(dir.join("workflow").join("THUMB.json"), "{}").unwrap();
        fs::write(dir.join("images").join("S2.png"), "png").unwrap();
        let hist = dir.join("history").join("gyroid").join("S2");
        fs::create_dir_all(&hist).unwrap();
        fs::write(
            hist.join("history.json"),
            serde_json::json!({"topic": "Gyroid", "scene_id": "S2", "attempts": []}).to_string(),
        )
        .unwrap();

        let scenes = list_scenes(&dir).unwrap();
        let ids: Vec<&str> = scenes.iter().map(|s| s.scene_id.as_str()).collect();
        assert_eq!(ids, vec!["S1", "S2", "S10", "THUMB"]);
        assert_eq!(scenes[0].image_path, None);
        assert!(scenes[1].image_path.as_deref().unwrap().ends_with("S2.png"));
        assert_eq!(
            scenes[1].history.as_ref().unwrap()["scene_id"],
            serde_json::json!("S2")
        );
        assert_eq!(scenes[0].history, None);
    }

    #[test]
    fn chain_maps_report_into_stage_order_with_pending_defaults() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = make_run(tmp.path(), "r1", "gyroid");
        let art = dir.join("artifacts").join("prompt_compiler");
        fs::create_dir_all(&art).unwrap();
        fs::write(
            art.join("output.1.json"),
            serde_json::json!({"prompt": "compiled"}).to_string(),
        )
        .unwrap();

        let stages = build_chain(&dir, Some(&report()));
        assert_eq!(stages.len(), 15);
        assert_eq!(stages[0].stage_id, "knowledge_load");
        assert_eq!(stages[0].name, "Knowledge Load");
        assert_eq!(stages[0].status, "completed");
        assert_eq!(stages[0].duration_ms, Some(120));
        assert_eq!(stages[0].cache_hit, Some(true));
        assert!(stages[0].artifact.is_none()); // no artifacts dir for it
        assert_eq!(stages[1].stage_id, "educational_director");
        assert_eq!(stages[1].status, "pending");
        assert_eq!(stages[5].stage_id, "prompt_compiler");
        assert!(stages[5].has_artifact);
        assert_eq!(stages[5].artifact.as_ref().unwrap()["prompt"], serde_json::json!("compiled"));
        assert_eq!(stages[5].duration_ms, Some(900));

        let no_report = build_chain(&dir, None);
        assert!(no_report.iter().all(|s| s.status == "pending"));
    }

    #[test]
    fn workflow_for_reads_and_validates_scene_id() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = make_run(tmp.path(), "r1", "gyroid");
        fs::write(
            dir.join("workflow").join("S1.json"),
            serde_json::json!({"profile": "sdxl", "sampler": "euler_a"}).to_string(),
        )
        .unwrap();

        let wf = workflow_for(tmp.path(), Some("r1"), "S1").unwrap();
        assert_eq!(wf["profile"], serde_json::json!("sdxl"));

        let err = workflow_for(tmp.path(), Some("r1"), "../etc/passwd").unwrap_err();
        assert!(err.starts_with("invalid_scene_id"), "got {err}");

        let err = workflow_for(tmp.path(), Some("r1"), "S9").unwrap_err();
        assert!(err.starts_with("read_error"), "got {err}");
    }

    #[test]
    fn export_workflow_round_trip_is_atomic_and_pretty() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = make_run(tmp.path(), "r1", "gyroid");
        fs::write(dir.join("workflow").join("S1.json"), r#"{"profile":"sdxl"}"#).unwrap();
        let out = tmp.path().join("exported.json");

        let wf = workflow_for(tmp.path(), Some("r1"), "S1").unwrap();
        let text = serde_json::to_string_pretty(&wf).unwrap();
        write_bytes_atomic(&out, text.as_bytes(), "export_workflow").unwrap();

        let loaded: serde_json::Value = read_json(&out).unwrap();
        assert_eq!(loaded["profile"], serde_json::json!("sdxl"));
        // no leftover tmp files
        let leftovers: Vec<_> = fs::read_dir(tmp.path())
            .unwrap()
            .flatten()
            .filter(|e| e.file_name().to_string_lossy().starts_with('.'))
            .collect();
        assert!(leftovers.is_empty(), "{leftovers:?}");
    }
}

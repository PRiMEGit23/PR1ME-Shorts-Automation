//! 2S2 `production_list` / `production_create` / `production_load` /
//! `production_save` / `production_import` — the production system.
//!
//! Each production lives at `config/productions/<slug>/production.json`
//! (product-owned, backend-untouched — UX_ARCHITECTURE §9.1). Writes are
//! atomic (tmp + rename). All paths are canonicalized; `run_dir` values
//! must stay under `<repo_root>/output/runs` (PRODUCT_LAYER §9).
//!
//! Commands are thin wrappers over pure functions so the model logic is
//! testable without a Tauri runtime (same pattern as settings/layout).

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::AppState;
use super::OkPayload;

// ---------------------------------------------------------------- model

/// Pipeline policy — pre-filled by templates (UI-side, UX §9.2).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PipelinePolicy {
    pub default_seed: u64,
    pub max_attempts: u32,
    pub publish_default: PublishDefault,
}

/// Publish default: `dryRun` | `real`.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum PublishDefault {
    DryRun,
    Real,
}

/// Default knowledge-base filters (prefilled by templates).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ProductionScope {
    pub category: Option<String>,
    pub difficulty: Option<String>,
}

/// Episode lifecycle (UX §9.1).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum EpisodeStatus {
    Drafted,
    Queued,
    Rendering,
    Review,
    Approved,
    Rendered,
    Delivered,
}

/// Run refs are empty until the first run exists.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Default)]
#[serde(rename_all = "camelCase")]
pub struct RunRefs {
    pub run_id: Option<String>,
    pub run_dir: Option<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct DeliverInfo {
    pub title_override: Option<String>,
    pub description_override: Option<String>,
    pub published: bool,
}

/// One Short = one KB row. Approvals map scene_id → candidate_id (or null).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct EpisodeRecord {
    pub topic: String,
    pub row_index: u32,
    pub status: EpisodeStatus,
    pub seed: Option<u64>,
    pub approvals: BTreeMap<String, Option<String>>,
    pub run: RunRefs,
    pub deliver: DeliverInfo,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ProductionIdentity {
    pub id: String,
    pub name: String,
    pub slug: String,
    pub created: String,
    pub updated: String,
}

/// UI-owned state: per-workbench layouts, palette recents (free-form JSON).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Default)]
#[serde(rename_all = "camelCase")]
pub struct ProductionUi {
    pub layouts: BTreeMap<String, serde_json::Value>,
    pub palette_recents: Vec<String>,
}

/// Full model persisted as `config/productions/<slug>/production.json`.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ProductionModel {
    pub identity: ProductionIdentity,
    pub policy: PipelinePolicy,
    pub scope: ProductionScope,
    pub episodes: Vec<EpisodeRecord>,
    pub ui: ProductionUi,
}

/// Library grid row (production_list).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ProductionSummary {
    pub id: String,
    pub name: String,
    pub slug: String,
    pub created: String,
    pub updated: String,
    pub episode_count: usize,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ProductionCreateArgs {
    pub name: String,
    pub template: Option<String>,
    pub policy: PipelinePolicy,
}

// ---------------------------------------------------------------- helpers

/// Lowercase alnum + dashes (mirror of `core/id.ts` slugify).
fn slugify(value: &str) -> String {
    let mut out = String::new();
    let mut dash = false;
    for ch in value.to_lowercase().chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch);
            dash = false;
        } else if !dash {
            out.push('-');
            dash = true;
        }
    }
    while out.ends_with('-') {
        out.pop();
    }
    while out.starts_with('-') {
        out.remove(0);
    }
    if out.len() > 64 {
        out.truncate(64);
        while out.ends_with('-') {
            out.pop();
        }
    }
    out
}

fn now_rfc3339() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format_rfc3339(secs)
}

/// Epoch seconds → RFC3339 UTC (no chrono dependency; Hinnant civil algorithm).
fn format_rfc3339(secs: u64) -> String {
    let days = secs / 86_400;
    let rem = secs % 86_400;
    let (h, m, s) = (rem / 3600, (rem % 3600) / 60, rem % 60);
    let z = days as i64 + 719_468;
    let era = (if z >= 0 { z } else { z - 146_096 }) / 146_097;
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let mo = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if mo <= 2 { yoe as i64 + era * 400 + 1 } else { yoe as i64 + era * 400 };
    format!("{y:04}-{mo:02}-{d:02}T{h:02}:{m:02}:{s:02}Z")
}

fn validate_policy(policy: &PipelinePolicy) -> Result<(), String> {
    if policy.max_attempts < 1 {
        return Err("policy.maxAttempts must be >= 1".to_string());
    }
    Ok(())
}

fn validate_name(name: &str) -> Result<String, String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err("name must not be empty".to_string());
    }
    let slug = slugify(trimmed);
    if slug.is_empty() {
        return Err("name does not contain any slug-safe characters".to_string());
    }
    Ok(slug)
}

fn validate_episodes(episodes: &[EpisodeRecord]) -> Result<(), String> {
    for (i, ep) in episodes.iter().enumerate() {
        if ep.topic.trim().is_empty() {
            return Err(format!("episodes[{i}].topic must not be empty"));
        }
    }
    Ok(())
}

/// run_dir must be canonical and stay under `<repo>/output/runs`.
fn validate_run_dirs(model: &ProductionModel, repo_root: &Path) -> Result<(), String> {
    let runs_root = repo_root
        .join("output")
        .join("runs")
        .canonicalize()
        .unwrap_or_else(|_| repo_root.join("output").join("runs"));
    for (i, ep) in model.episodes.iter().enumerate() {
        if let Some(dir) = &ep.run.run_dir {
            let canonical = fs::canonicalize(dir).map_err(|e| e.to_string())?;
            if !canonical.starts_with(&runs_root) {
                return Err(format!(
                    "episodes[{i}].run.runDir must live under output/runs"
                ));
            }
        }
    }
    Ok(())
}

fn production_path(productions_dir: &Path, slug: &str) -> PathBuf {
    productions_dir.join(slug).join("production.json")
}

fn atomic_write_json(path: &Path, model: &ProductionModel) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "production path has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;

    let json = serde_json::to_string_pretty(model).map_err(|e| e.to_string())?;
    let tmp = parent.join("production.json.tmp");
    fs::write(&tmp, json).map_err(|e| format!("write {}: {e}", tmp.display()))?;

    // Windows rename fails when the destination exists — replace it.
    if path.exists() {
        fs::remove_file(path).map_err(|e| format!("replace {}: {e}", path.display()))?;
    }
    fs::rename(&tmp, path).map_err(|e| format!("rename: {e}"))?;
    Ok(())
}

fn read_model(path: &Path) -> Result<ProductionModel, String> {
    let text = fs::read_to_string(path)
        .map_err(|e| format!("read {}: {e}", path.display()))?;
    serde_json::from_str(&text).map_err(|e| format!("parse {}: {e}", path.display()))
}

fn summary(model: &ProductionModel) -> ProductionSummary {
    ProductionSummary {
        id: model.identity.id.clone(),
        name: model.identity.name.clone(),
        slug: model.identity.slug.clone(),
        created: model.identity.created.clone(),
        updated: model.identity.updated.clone(),
        episode_count: model.episodes.len(),
    }
}

fn list_models(productions_dir: &Path) -> Result<Vec<ProductionModel>, String> {
    let mut models = Vec::new();
    if !productions_dir.exists() {
        return Ok(models);
    }
    let entries = fs::read_dir(productions_dir).map_err(|e| e.to_string())?;
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        if !entry.path().is_dir() {
            continue;
        }
        let file = entry.path().join("production.json");
        if file.exists() {
            if let Ok(model) = read_model(&file) {
                models.push(model);
            }
        }
    }
    models.sort_by(|a, b| a.identity.name.cmp(&b.identity.name));
    Ok(models)
}

fn new_identity(name: &str, slug: String) -> ProductionIdentity {
    let now = now_rfc3339();
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0);
    ProductionIdentity {
        id: format!("pr1me-{slug}-{nanos:x}"),
        name: name.trim().to_string(),
        slug,
        created: now.clone(),
        updated: now,
    }
}

// ------------------------------------------------------------ pure logic

/// Library grid: every production's summary (sorted by name).
pub fn list_productions(productions_dir: &Path) -> Result<Vec<ProductionSummary>, String> {
    Ok(list_models(productions_dir)?
        .into_iter()
        .map(|m| summary(&m))
        .collect())
}

/// Create a production. `template` is accepted but not stored — templates
/// prefill the policy UI-side (UX §9.2, "no backend involvement").
pub fn create_production(
    productions_dir: &Path,
    args: ProductionCreateArgs,
) -> Result<ProductionModel, String> {
    let slug = validate_name(&args.name)?;
    validate_policy(&args.policy)?;

    let path = production_path(productions_dir, &slug);
    if path.exists() {
        return Err(format!("production '{slug}' already exists"));
    }

    let model = ProductionModel {
        identity: new_identity(&args.name, slug),
        policy: args.policy,
        scope: ProductionScope {
            category: None,
            difficulty: None,
        },
        episodes: Vec::new(),
        ui: ProductionUi::default(),
    };

    atomic_write_json(&path, &model)?;
    Ok(model)
}

/// Scope the window to a production (Library → Explorer/Script/Queue/Inspector).
pub fn load_production(
    productions_dir: &Path,
    production_id: &str,
) -> Result<ProductionModel, String> {
    let models = list_models(productions_dir)?;
    models
        .into_iter()
        .find(|m| m.identity.id == production_id)
        .ok_or_else(|| format!("production '{production_id}' not found"))
}

/// Full-model save: approvals/policy/episodes are product-owned (atomic).
pub fn save_production(
    repo_root: &Path,
    productions_dir: &Path,
    model: ProductionModel,
) -> Result<ProductionModel, String> {
    let slug = validate_name(&model.identity.name)?;
    if slug != model.identity.slug {
        return Err("identity.slug does not match identity.name".to_string());
    }
    validate_policy(&model.policy)?;
    validate_episodes(&model.episodes)?;
    validate_run_dirs(&model, repo_root)?;

    let path = production_path(productions_dir, &slug);
    if !path.exists() {
        return Err(format!("production '{slug}' not found"));
    }

    let mut model = model;
    model.identity.updated = now_rfc3339();
    atomic_write_json(&path, &model)?;
    Ok(model)
}

/// Adopt the existing `output/runs/*` tree as episodes (UX §9.2 import).
/// Each run dir containing a manifest.json becomes one EpisodeRecord.
pub fn import_production(
    repo_root: &Path,
    productions_dir: &Path,
    name: &str,
) -> Result<ProductionModel, String> {
    let slug = validate_name(name)?;
    let path = production_path(productions_dir, &slug);
    if path.exists() {
        return Err(format!("production '{slug}' already exists"));
    }

    let runs_root = repo_root.join("output").join("runs");
    let mut episodes = Vec::new();
    if runs_root.exists() {
        let entries = fs::read_dir(&runs_root).map_err(|e| e.to_string())?;
        for entry in entries {
            let entry = entry.map_err(|e| e.to_string())?;
            let dir = entry.path();
            if !dir.is_dir() {
                continue;
            }
            let manifest_path = dir.join("manifest.json");
            let Ok(manifest_text) = fs::read_to_string(&manifest_path) else {
                continue;
            };
            let Ok(manifest) = serde_json::from_str::<serde_json::Value>(&manifest_text) else {
                continue;
            };
            let topic = manifest
                .get("topic")
                .and_then(|v| v.as_str())
                .map(str::to_string)
                .unwrap_or_else(|| {
                    dir.file_name()
                        .map(|f| f.to_string_lossy().to_string())
                        .unwrap_or_default()
                });
            let run_id = manifest.get("run_id").and_then(|v| v.as_str()).map(str::to_string);
            let run_dir = Some(dir.to_string_lossy().to_string());
            episodes.push(EpisodeRecord {
                topic,
                row_index: episodes.len() as u32,
                status: EpisodeStatus::Rendered,
                seed: None,
                approvals: BTreeMap::new(),
                run: RunRefs { run_id, run_dir },
                deliver: DeliverInfo {
                    title_override: None,
                    description_override: None,
                    published: false,
                },
            });
        }
    }

    if episodes.is_empty() {
        return Err("no runs found under output/runs to adopt".to_string());
    }

    let model = ProductionModel {
        identity: new_identity(name, slug),
        policy: PipelinePolicy {
            default_seed: 1,
            max_attempts: 3,
            publish_default: PublishDefault::DryRun,
        },
        scope: ProductionScope {
            category: None,
            difficulty: None,
        },
        episodes,
        ui: ProductionUi::default(),
    };

    atomic_write_json(&path, &model)?;
    Ok(model)
}

// ---------------------------------------------------------------- commands

#[tauri::command]
pub async fn production_list(state: State<'_, AppState>) -> Result<Vec<ProductionSummary>, String> {
    list_productions(&state.productions_dir)
}

#[tauri::command]
pub async fn production_create(
    state: State<'_, AppState>,
    args: ProductionCreateArgs,
) -> Result<ProductionModel, String> {
    create_production(&state.productions_dir, args)
}

#[tauri::command]
pub async fn production_load(
    state: State<'_, AppState>,
    production_id: String,
) -> Result<ProductionModel, String> {
    load_production(&state.productions_dir, &production_id)
}

#[tauri::command]
pub async fn production_save(
    state: State<'_, AppState>,
    model: ProductionModel,
) -> Result<OkPayload, String> {
    save_production(&state.repo_root, &state.productions_dir, model)?;
    Ok(OkPayload { ok: true })
}

#[tauri::command]
pub async fn production_import(
    state: State<'_, AppState>,
    name: String,
) -> Result<ProductionModel, String> {
    import_production(&state.repo_root, &state.productions_dir, &name)
}

// ---------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    fn dirs(repo: &Path) -> (PathBuf, PathBuf) {
        (
            repo.join("config").join("productions"),
            repo.join("output").join("runs"),
        )
    }

    fn policy() -> PipelinePolicy {
        PipelinePolicy {
            default_seed: 1,
            max_attempts: 3,
            publish_default: PublishDefault::DryRun,
        }
    }

    fn episode(topic: &str, row_index: u32) -> EpisodeRecord {
        EpisodeRecord {
            topic: topic.to_string(),
            row_index,
            status: EpisodeStatus::Drafted,
            seed: None,
            approvals: BTreeMap::new(),
            run: RunRefs::default(),
            deliver: DeliverInfo {
                title_override: None,
                description_override: None,
                published: false,
            },
        }
    }

    fn model(slug: &str) -> ProductionModel {
        ProductionModel {
            identity: ProductionIdentity {
                id: format!("pr1me-{slug}"),
                name: slug.replace('-', " "),
                slug: slug.to_string(),
                created: "2026-01-01T00:00:00Z".to_string(),
                updated: "2026-01-01T00:00:00Z".to_string(),
            },
            policy: policy(),
            scope: ProductionScope {
                category: None,
                difficulty: None,
            },
            episodes: vec![episode("Layer Height", 0)],
            ui: ProductionUi::default(),
        }
    }

    #[test]
    fn slugify_matches_frontend_rules() {
        assert_eq!(slugify("Layer Height"), "layer-height");
        assert_eq!(slugify("  FDM Photoreal!  "), "fdm-photoreal");
        assert_eq!(slugify("123"), "123");
        assert_eq!(slugify(""), "");
        assert_eq!(slugify(&"a".repeat(80)).len(), 64);
    }

    #[test]
    fn rfc3339_formats_epoch() {
        assert_eq!(format_rfc3339(0), "1970-01-01T00:00:00Z");
        assert_eq!(format_rfc3339(1_752_624_000), "2025-07-16T00:00:00Z");
    }

    #[test]
    fn validation_rejects_bad_input() {
        assert!(validate_name("  ").is_err());
        assert!(validate_name("!!!").is_err());
        assert!(validate_name("Layer Height").is_ok());

        let mut bad = policy();
        bad.max_attempts = 0;
        assert!(validate_policy(&bad).is_err());
        assert!(validate_policy(&policy()).is_ok());

        let ep = episode("", 0);
        assert!(validate_episodes(&[ep]).is_err());
    }

    #[test]
    fn serde_round_trip_matches_frontend_shape() {
        let json = serde_json::to_value(model("layer-height")).unwrap();
        let obj = json.as_object().unwrap();
        for key in ["identity", "policy", "scope", "episodes", "ui"] {
            assert!(obj.contains_key(key), "missing key {key}");
        }
        let id = obj["identity"].as_object().unwrap();
        for key in ["id", "name", "slug", "created", "updated"] {
            assert!(id.contains_key(key), "missing identity key {key}");
        }
        let pol = obj["policy"].as_object().unwrap();
        for key in ["defaultSeed", "maxAttempts", "publishDefault"] {
            assert!(pol.contains_key(key), "missing policy key {key}");
        }
        assert_eq!(pol["publishDefault"], "dryRun");
        let ep = &obj["episodes"][0];
        assert_eq!(ep["status"], "drafted");
        assert_eq!(ep["rowIndex"], 0);
        let back: ProductionModel = serde_json::from_value(json).unwrap();
        assert_eq!(back, model("layer-height"));
    }

    #[test]
    fn create_list_load_round_trip() {
        let repo = tempfile::tempdir().unwrap();
        let (prod_dir, _) = dirs(repo.path());

        let args = ProductionCreateArgs {
            name: "Layer Height".to_string(),
            template: Some("default".to_string()),
            policy: policy(),
        };
        let created = create_production(&prod_dir, args).map_err(|e| panic!("{e}")).unwrap();
        assert_eq!(created.identity.slug, "layer-height");
        assert_eq!(created.episodes.len(), 0);

        let path = prod_dir.join("layer-height").join("production.json");
        assert!(path.exists());
        let on_disk: ProductionModel =
            serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(on_disk.identity.slug, "layer-height");

        let listed = list_productions(&prod_dir).map_err(|e| panic!("{e}")).unwrap();
        assert_eq!(listed.len(), 1);
        assert_eq!(listed[0].id, created.identity.id);
        assert_eq!(listed[0].episode_count, 0);

        let loaded =
            load_production(&prod_dir, &created.identity.id).map_err(|e| panic!("{e}")).unwrap();
        assert_eq!(loaded, created);
    }

    #[test]
    fn duplicate_create_is_rejected() {
        let repo = tempfile::tempdir().unwrap();
        let (prod_dir, _) = dirs(repo.path());

        let args = ProductionCreateArgs {
            name: "Batch Campaign".to_string(),
            template: None,
            policy: policy(),
        };
        create_production(&prod_dir, args.clone()).map_err(|e| panic!("{e}")).unwrap();
        let err = create_production(&prod_dir, args).unwrap_err();
        assert!(err.contains("already exists"));
    }

    #[test]
    fn save_requires_matching_slug_and_valid_run_dirs() {
        let repo = tempfile::tempdir().unwrap();
        let (prod_dir, runs_dir) = dirs(repo.path());

        let args = ProductionCreateArgs {
            name: "Layer Height".to_string(),
            template: None,
            policy: policy(),
        };
        let created = create_production(&prod_dir, args).map_err(|e| panic!("{e}")).unwrap();

        let mut renamed = created.clone();
        renamed.identity.name = "Other Name".to_string();
        let err = save_production(repo.path(), &prod_dir, renamed).unwrap_err();
        assert!(err.contains("does not match"));

        let mut bad_policy = created.clone();
        bad_policy.policy.max_attempts = 0;
        assert!(save_production(repo.path(), &prod_dir, bad_policy).is_err());

        let mut bad_run = created.clone();
        bad_run.episodes.push(episode("Layer Height", 0));
        let elsewhere = repo.path().join("elsewhere");
        fs::create_dir_all(&elsewhere).unwrap();
        bad_run.episodes[0].run.run_dir = Some(elsewhere.to_string_lossy().to_string());
        let err = save_production(repo.path(), &prod_dir, bad_run).unwrap_err();
        assert!(err.contains("output/runs"));

        let good_run = runs_dir.join("gyroid");
        fs::create_dir_all(&good_run).unwrap();
        let mut good = created.clone();
        good.episodes.push(episode("Infill", 1));
        good.episodes[0].run.run_dir = Some(good_run.to_string_lossy().to_string());
        good.policy.default_seed = 7;
        save_production(repo.path(), &prod_dir, good).map_err(|e| panic!("{e}")).unwrap();

        let loaded =
            load_production(&prod_dir, &created.identity.id).map_err(|e| panic!("{e}")).unwrap();
        assert_eq!(loaded.episodes.len(), 1);
        assert_eq!(loaded.policy.default_seed, 7);
        assert!(loaded.identity.updated.ends_with('Z'));
        let on_disk: ProductionModel = serde_json::from_str(
            &fs::read_to_string(prod_dir.join("layer-height").join("production.json")).unwrap(),
        )
        .unwrap();
        assert_eq!(on_disk, loaded);
    }

    #[test]
    fn atomic_write_preserves_content() {
        let repo = tempfile::tempdir().unwrap();
        let (prod_dir, _) = dirs(repo.path());
        let path = prod_dir.join("a").join("production.json");
        let a = model("a");
        let mut b = model("a");
        b.policy.default_seed = 9;
        atomic_write_json(&path, &a).unwrap();
        atomic_write_json(&path, &b).unwrap();
        let on_disk: ProductionModel =
            serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(on_disk.policy.default_seed, 9);
    }

    #[test]
    fn import_adopts_runs_tree() {
        let repo = tempfile::tempdir().unwrap();
        let (prod_dir, runs_dir) = dirs(repo.path());
        let runs = runs_dir.join("gyroid");
        fs::create_dir_all(&runs).unwrap();
        fs::write(
            runs.join("manifest.json"),
            r#"{"version":"7.0.0","run_id":"r-1","job_id":"j-1","topic":"Gyroid","status":"completed","run_dir":"out"}"#,
        )
        .unwrap();

        let imported = import_production(repo.path(), &prod_dir, "Adopted")
            .map_err(|e| panic!("{e}"))
            .unwrap();
        assert_eq!(imported.episodes.len(), 1);
        assert_eq!(imported.episodes[0].topic, "Gyroid");
        assert_eq!(imported.episodes[0].status, EpisodeStatus::Rendered);
        assert_eq!(imported.episodes[0].run.run_id.as_deref(), Some("r-1"));
        assert!(imported.episodes[0].run.run_dir.as_deref().unwrap().contains("gyroid"));

        let err = import_production(repo.path(), &prod_dir, "Adopted").unwrap_err();
        assert!(err.contains("already exists"));
    }

    #[test]
    fn import_rejects_when_no_runs() {
        let repo = tempfile::tempdir().unwrap();
        let (prod_dir, _) = dirs(repo.path());
        let err = import_production(repo.path(), &prod_dir, "Empty").unwrap_err();
        assert!(err.contains("no runs found"));
    }
}
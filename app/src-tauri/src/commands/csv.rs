//! 2S3 CSV wrappers — `load_csv` / `save_csv` / `validate_csv` /
//! `import_csv` / `export_csv` / `search_csv`.
//!
//! Rust performs filesystem access ONLY (PRODUCT_LAYER §4): RFC4180 parse
//! (hand-rolled state machine, no csv crate), paged reads, atomic writes
//! (tmp + rename, exclusive mutex lock), a windowed substring search, and
//! `validate_csv` spawning the Python validator as an isolated process —
//! NO validation logic lives in Rust (BACKEND_ARCHITECTURE §7.2).
//!
//! Commands are thin wrappers over pure functions so parsing/writing is
//! testable without a Tauri runtime (same pattern as settings/productions).

use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::AppState;
use super::OkPayload;

/// Import/export size cap (5 MB) — SECURITY §10 "size limits".
const MAX_CSV_BYTES: u64 = 5 * 1024 * 1024;
/// Max rows per paged read / export.
const MAX_PAGE: usize = 10_000;
/// Validator wall-clock cap.
const VALIDATOR_TIMEOUT: Duration = Duration::from_secs(30);

// ---------------------------------------------------------------- model

/// One paged slice of a CSV file (PRODUCT_LAYER §6 `csv_read` contract).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct CsvPage {
    pub header: Vec<String>,
    pub rows: Vec<Vec<String>>,
    pub total: usize,
}

/// A single validation issue (row is 1-based data row; column = header name).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ValidationIssue {
    pub row: usize,
    pub column: String,
    pub code: String,
    pub message: String,
}

/// Contract emitted by `validate_knowledge_csv.py` on stdout (JSON).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ValidationReport {
    pub valid: bool,
    pub checked_at: String,
    pub errors: Vec<ValidationIssue>,
    pub warnings: Vec<ValidationIssue>,
}

// ------------------------------------------------------- csv parsing

/// RFC4180 parse: quoted fields, `""` escapes, embedded commas/newlines,
/// CRLF or LF endings, optional UTF-8 BOM. Returns (header, rows).
fn parse_csv(text: &str) -> Result<(Vec<String>, Vec<Vec<String>>), String> {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let mut fields: Vec<String> = Vec::new();
    let mut records: Vec<Vec<String>> = Vec::new();
    let mut field = String::new();
    let mut in_quotes = false;
    let mut after_quote = false;
    // True when no character has been consumed since the last record end —
    // blank lines (trailing or embedded) must not produce empty records.
    let mut at_record_start = true;
    let mut chars = text.chars().peekable();

    while let Some(ch) = chars.next() {
        if in_quotes {
            match ch {
                '"' => {
                    if chars.peek() == Some(&'"') {
                        field.push('"');
                        chars.next();
                    } else {
                        in_quotes = false;
                        after_quote = true;
                    }
                }
                _ => field.push(ch),
            }
        } else {
            match ch {
                '"' if field.is_empty() && !after_quote => {
                    in_quotes = true;
                    at_record_start = false;
                }
                '"' => {
                    // stray quote mid-field: keep literal (lenient)
                    field.push('"');
                    at_record_start = false;
                }
                ',' => {
                    fields.push(std::mem::take(&mut field));
                    after_quote = false;
                    at_record_start = false;
                }
                '\r' => {
                    if chars.peek() == Some(&'\n') {
                        chars.next();
                    }
                    if !at_record_start {
                        fields.push(std::mem::take(&mut field));
                        records.push(std::mem::take(&mut fields));
                        at_record_start = true;
                    }
                    after_quote = false;
                }
                '\n' => {
                    if !at_record_start {
                        fields.push(std::mem::take(&mut field));
                        records.push(std::mem::take(&mut fields));
                        at_record_start = true;
                    }
                    after_quote = false;
                }
                _ => {
                    field.push(ch);
                    at_record_start = false;
                }
            }
        }
    }
    // trailing field without newline
    if !at_record_start {
        fields.push(std::mem::take(&mut field));
        if !fields.is_empty() {
            records.push(std::mem::take(&mut fields));
        }
    }

    let mut records = records.into_iter();
    let header = records
        .next()
        .ok_or_else(|| "csv_parse: file is empty".to_string())?;
    let rows: Vec<Vec<String>> = records.collect();
    Ok((header, rows))
}

/// RFC4180 serialize: quote when a field contains comma/quote/CR/LF.
fn serialize_csv(header: &[String], rows: &[Vec<String>]) -> String {
    fn quote(field: &str) -> String {
        if field.contains(',') || field.contains('"') || field.contains('\r') || field.contains('\n')
        {
            format!("\"{}\"", field.replace('"', "\"\""))
        } else {
            field.to_string()
        }
    }
    let mut out = String::new();
    out.push_str(&header.iter().map(|f| quote(f)).collect::<Vec<_>>().join(","));
    out.push_str("\r\n");
    for row in rows {
        out.push_str(&row.iter().map(|f| quote(f)).collect::<Vec<_>>().join(","));
        out.push_str("\r\n");
    }
    out
}

/// Atomic write: tmp file + rename (Windows: remove-then-rename).
/// The caller holds the app-wide `csv_lock` — exclusive lock (§9).
fn write_csv_atomic(lock: &Mutex<()>, path: &Path, text: &str) -> Result<(), String> {
    let _guard = lock.lock().map_err(|e| format!("csv_lock poisoned: {e}"))?;
    super::write_bytes_atomic(path, text.as_bytes(), "csv_write")
}

/// Path guard: KB manager operates on `assets/` only (BACKEND §10).
/// The assets dir itself is canonicalized; the relative remainder is
/// validated lexically (no `..`, no absolute) and appended.
fn resolve_assets_path(repo_root: &Path, rel: &str) -> Result<PathBuf, String> {
    let rel_path = Path::new(rel);
    if rel_path.is_absolute()
        || rel_path
            .components()
            .any(|c| matches!(c, Component::ParentDir | Component::RootDir | Component::Prefix(_)))
    {
        return Err(format!("csv path must live under assets/ (got {rel:?})"));
    }
    let assets = fs::canonicalize(repo_root.join("assets"))
        .map_err(|e| format!("csv path: repo assets dir: {e}"))?;
    Ok(assets.join(rel_path))
}

/// Load + parse a CSV file (pure).
fn read_csv_file(path: &Path) -> Result<(Vec<String>, Vec<Vec<String>>), String> {
    let meta = fs::metadata(path).map_err(|e| format!("csv_read: {e}"))?;
    if meta.len() > MAX_CSV_BYTES {
        return Err(format!("csv_read: file exceeds {MAX_CSV_BYTES} bytes"));
    }
    let text = fs::read_to_string(path).map_err(|e| format!("csv_read: {e}"))?;
    let (header, rows) = parse_csv(&text).map_err(|e| format!("csv_read: {e}"))?;
    if header.is_empty() {
        return Err("csv_read: empty header".to_string());
    }
    Ok((header, rows))
}

/// Windowed slice (pure).
fn page_rows(rows: &[Vec<String>], offset: usize, limit: usize) -> (Vec<Vec<String>>, usize) {
    let total = rows.len();
    let offset = offset.min(total);
    let end = (offset + limit).min(total);
    (rows[offset..end].to_vec(), total)
}

/// Case-insensitive substring scan across every cell (pure).
/// `header` is accepted for API symmetry with `read_csv_file` (the search
/// covers all cells of every row).
fn search_rows(
    header: &[String],
    rows: &[Vec<String>],
    query: &str,
    offset: usize,
    limit: usize,
) -> (Vec<Vec<String>>, usize) {
    debug_assert!(!header.is_empty());
    let q = query.trim().to_lowercase();
    let hits: Vec<&Vec<String>> = if q.is_empty() {
        rows.iter().collect()
    } else {
        rows.iter()
            .filter(|row| row.iter().any(|cell| cell.to_lowercase().contains(&q)))
            .collect()
    };
    let total = hits.len();
    let start = offset.min(total);
    let end = (start + limit).min(total);
    let page: Vec<Vec<String>> = hits[start..end].iter().map(|r| (*r).clone()).collect();
    (page, total)
}

fn resolve_on_path(name: &str) -> Option<PathBuf> {
    let paths = std::env::var_os("PATH")?;
    let mut probes = vec![name.to_string()];
    if cfg!(windows) {
        probes.push(format!("{name}.exe"));
        probes.push(format!("{name}.cmd"));
        probes.push(format!("{name}.bat"));
    }
    for dir in std::env::split_paths(&paths) {
        for probe in &probes {
            let candidate = dir.join(probe);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

/// Python interpreter: repo `.venv` first (same as the pr1me sidecar),
/// then PATH, then the bare `python` name.
fn resolve_python(repo_root: &Path) -> PathBuf {
    if cfg!(windows) {
        let scripts = repo_root.join(".venv").join("Scripts");
        for name in ["python.exe", "python.cmd", "python.bat"] {
            let candidate = scripts.join(name);
            if candidate.is_file() {
                return candidate;
            }
        }
    } else {
        let bin = repo_root.join(".venv").join("bin");
        for name in ["python", "python3"] {
            let candidate = bin.join(name);
            if candidate.is_file() {
                return candidate;
            }
        }
    }
    if let Some(found) = resolve_on_path("python") {
        return found;
    }
    if cfg!(windows) {
        PathBuf::from("python.exe")
    } else {
        PathBuf::from("python3")
    }
}

/// Invoke `validate_knowledge_csv.py <path>` as an isolated process
/// (BACKEND_ARCHITECTURE §1/§7.2). Resolution: repo root → PATH, like the
/// pr1me sidecar. The script owns ALL validation; we only relay its JSON.
fn run_validator(repo_root: &Path, csv_path: &Path) -> Result<ValidationReport, String> {
    let name = "validate_knowledge_csv.py";
    let script = repo_root
        .join(name)
        .canonicalize()
        .ok()
        .filter(|p| p.is_file())
        .or_else(|| resolve_on_path(name))
        .ok_or_else(|| format!("validator_missing: {name} not found in repo root or PATH"))?;

    let mut child = Command::new(resolve_python(repo_root))
        .arg(&script)
        .arg(csv_path)
        .current_dir(repo_root)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| format!("validator_spawn: {e}"))?;

    let deadline = Instant::now() + VALIDATOR_TIMEOUT;
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) => {
                if Instant::now() >= deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err("validator_timeout: took > 30 s".to_string());
                }
                std::thread::sleep(Duration::from_millis(25));
            }
            Err(e) => return Err(format!("validator_wait: {e}")),
        }
    };

    use std::io::Read;
    let mut out = String::new();
    let mut err = String::new();
    child
        .stdout
        .take()
        .and_then(|mut o| o.read_to_string(&mut out).ok())
        .ok_or_else(|| "validator_io: stdout".to_string())?;
    child
        .stderr
        .take()
        .and_then(|mut o| o.read_to_string(&mut err).ok())
        .ok_or_else(|| "validator_io: stderr".to_string())?;

    if !status.success() {
        let tail = err.trim();
        return Err(format!(
            "validator_exit: code {} · {}",
            status.code().unwrap_or(-1),
            if tail.is_empty() { out.trim() } else { tail }
        ));
    }
    serde_json::from_str(out.trim())
        .map_err(|e| format!("validator_report: invalid JSON on stdout: {e}"))
}

// ------------------------------------------------------------ commands

/// `assets/<rel>` paged read (KB manager, PRODUCT_LAYER §6).
#[tauri::command]
pub async fn load_csv(
    state: State<'_, AppState>,
    path: String,
    offset: usize,
    limit: usize,
) -> Result<CsvPage, String> {
    let limit = limit.min(MAX_PAGE);
    let path = resolve_assets_path(&state.repo_root, &path)?;
    let (header, rows) = read_csv_file(&path)?;
    let (rows, total) = page_rows(&rows, offset, limit);
    Ok(CsvPage {
        header,
        rows,
        total,
    })
}

/// `assets/<rel>` atomic write with exclusive lock.
#[tauri::command]
pub async fn save_csv(
    state: State<'_, AppState>,
    path: String,
    header: Vec<String>,
    rows: Vec<Vec<String>>,
) -> Result<OkPayload, String> {
    let path = resolve_assets_path(&state.repo_root, &path)?;
    if header.is_empty() {
        return Err("csv_save: header must not be empty".to_string());
    }
    let text = serialize_csv(&header, &rows);
    write_csv_atomic(&state.csv_lock, &path, &text)?;
    Ok(OkPayload { ok: true })
}

/// Run the Python validator over `assets/<rel>`; report relayed verbatim.
#[tauri::command]
pub async fn validate_csv(
    state: State<'_, AppState>,
    path: String,
) -> Result<ValidationReport, String> {
    let path = resolve_assets_path(&state.repo_root, &path)?;
    run_validator(&state.repo_root, &path)
}

/// `import_csv`: read + parse ANY user-picked CSV (OS dialog path) for
/// preview; nothing is written — the caller confirms, then `save_csv`
/// persists the data into `assets/` (safe overwrite flow).
#[tauri::command]
pub async fn import_csv(path: String) -> Result<CsvPage, String> {
    let path = PathBuf::from(&path);
    if !path.is_file() {
        return Err(format!("import_csv: not a file: {}", path.display()));
    }
    let (header, rows) = read_csv_file(&path)?;
    let total = rows.len();
    Ok(CsvPage {
        header,
        rows,
        total,
    })
}

/// `export_csv`: atomic write of a table to ANY user-picked destination.
#[tauri::command]
pub async fn export_csv(
    path: String,
    header: Vec<String>,
    rows: Vec<Vec<String>>,
) -> Result<OkPayload, String> {
    let path = PathBuf::from(&path);
    if header.is_empty() {
        return Err("csv_export: header must not be empty".to_string());
    }
    if rows.len() > MAX_PAGE {
        return Err(format!("csv_export: too many rows (max {MAX_PAGE})"));
    }
    let text = serialize_csv(&header, &rows);
    let lock = Mutex::new(());
    write_csv_atomic(&lock, &path, &text)?;
    Ok(OkPayload { ok: true })
}

/// `search_csv`: windowed case-insensitive scan of `assets/<rel>`.
#[tauri::command]
pub async fn search_csv(
    state: State<'_, AppState>,
    path: String,
    query: String,
    offset: usize,
    limit: usize,
) -> Result<CsvPage, String> {
    let limit = limit.min(MAX_PAGE);
    let path = resolve_assets_path(&state.repo_root, &path)?;
    let (header, rows) = read_csv_file(&path)?;
    let (rows, total) = search_rows(&header, &rows, &query, offset, limit);
    Ok(CsvPage {
        header,
        rows,
        total,
    })
}

// ---------------------------------------------------- locked-table aliases
// The PRODUCT_LAYER IPC table names the same operations `csv_read` /
// `csv_write` / `csv_validate`; keep them as thin aliases so both
// contracts hold.

#[tauri::command]
pub async fn csv_read(
    state: State<'_, AppState>,
    path: String,
    offset: usize,
    limit: usize,
) -> Result<CsvPage, String> {
    load_csv(state, path, offset, limit).await
}

#[tauri::command]
pub async fn csv_write(
    state: State<'_, AppState>,
    path: String,
    header: Vec<String>,
    rows: Vec<Vec<String>>,
) -> Result<OkPayload, String> {
    save_csv(state, path, header, rows).await
}

#[tauri::command]
pub async fn csv_validate(
    state: State<'_, AppState>,
    path: String,
) -> Result<ValidationReport, String> {
    validate_csv(state, path).await
}

// --------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_simple_csv() {
        let text = "topic,difficulty,category\r\nA,B,C\r\nD,E,F\r\n";
        let (header, rows) = parse_csv(text).unwrap();
        assert_eq!(header, vec!["topic", "difficulty", "category"]);
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0], vec!["A", "B", "C"]);
        assert_eq!(rows[1], vec!["D", "E", "F"]);
    }

    #[test]
    fn parses_quoted_fields_with_commas_quotes_and_newlines() {
        let text = "topic,json\r\n\"Bed Adhesion\",\"{\"\"a\"\": 1, \"\"b\"\": [1, 2]}\"\r\n\"A\nB\",\"plain\"\r\n";
        let (header, rows) = parse_csv(text).unwrap();
        assert_eq!(header, vec!["topic", "json"]);
        assert_eq!(rows[0][0], "Bed Adhesion");
        assert_eq!(rows[0][1], "{\"a\": 1, \"b\": [1, 2]}");
        assert_eq!(rows[1][0], "A\nB");
    }

    #[test]
    fn parses_lf_only_and_bom() {
        let text = "\u{feff}a,b\n1,2\n3,4\n";
        let (header, rows) = parse_csv(text).unwrap();
        assert_eq!(header, vec!["a", "b"]);
        assert_eq!(rows.len(), 2);
    }

    #[test]
    fn parses_trailing_empty_lines() {
        let text = "a,b\n1,2\n\n\n";
        let (_, rows) = parse_csv(text).unwrap();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0], vec!["1", "2"]);
    }

    #[test]
    fn serialize_quotes_only_when_needed() {
        let header = vec!["topic".to_string(), "json".to_string()];
        let rows = vec![
            vec!["plain".to_string(), "{\"a\": 1}".to_string()],
            vec!["with, comma".to_string(), "quote\"here".to_string()],
        ];
        let out = serialize_csv(&header, &rows);
        assert!(out.contains("\"with, comma\""));
        assert!(out.contains("\"quote\"\"here\""));
        assert!(out.contains("plain,"));
    }

    #[test]
    fn round_trip_knowledge_row() {
        let header = vec![
            "topic".to_string(),
            "keywords".to_string(),
            "scene_plan_json".to_string(),
        ];
        let rows = vec![vec![
            "Bed Adhesion".to_string(),
            "adhesion;bed level".to_string(),
            "[{\"scene_id\":1,\"duration\":3}]".to_string(),
        ]];
        let text = serialize_csv(&header, &rows);
        let (h2, r2) = parse_csv(&text).unwrap();
        assert_eq!(h2, header);
        assert_eq!(r2, rows);
    }

    #[test]
    fn page_rows_windows_and_clamps_offset() {
        let rows: Vec<Vec<String>> = (0..10).map(|i| vec![i.to_string()]).collect();
        let (page, total) = page_rows(&rows, 3, 4);
        assert_eq!(total, 10);
        assert_eq!(page.len(), 4);
        assert_eq!(page[0], vec!["3"]);
        let (page, total) = page_rows(&rows, 100, 4);
        assert_eq!(total, 10);
        assert_eq!(page.len(), 0);
    }

    #[test]
    fn search_matches_any_cell_case_insensitively() {
        let header = vec!["topic".to_string(), "keywords".to_string()];
        let rows = vec![
            vec!["Bed Adhesion".to_string(), "bed;first layer".to_string()],
            vec!["Infill".to_string(), "density".to_string()],
            vec!["Filament".to_string(), "bed temperature".to_string()],
        ];
        let (hits, total) = search_rows(&header, &rows, "BED", 0, 10);
        assert_eq!(total, 2); // row 1 (topic) + row 3 (keywords)
        assert_eq!(hits.len(), 2);
        let (hits, total) = search_rows(&header, &rows, "zzz", 0, 10);
        assert_eq!(total, 0);
        assert!(hits.is_empty());
        let (hits, total) = search_rows(&header, &rows, "", 0, 1);
        assert_eq!(total, 3);
        assert_eq!(hits.len(), 1);
    }

    #[test]
    fn write_is_atomic_and_readable() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("knowledge_base.csv");
        let lock = Mutex::new(());
        let text = "a,b\r\n1,2\r\n";
        write_csv_atomic(&lock, &path, text).unwrap();
        assert_eq!(fs::read_to_string(&path).unwrap(), text);
        let leftovers: Vec<_> = fs::read_dir(dir.path())
            .unwrap()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_name().to_string_lossy().ends_with(".tmp"))
            .collect();
        assert!(leftovers.is_empty(), "tmp files must be renamed away");
    }

    #[test]
    fn overwrite_replaces_content() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("a.csv");
        let lock = Mutex::new(());
        write_csv_atomic(&lock, &path, "x\r\n").unwrap();
        write_csv_atomic(&lock, &path, "y\r\n").unwrap();
        assert_eq!(fs::read_to_string(&path).unwrap(), "y\r\n");
    }

    #[test]
    fn read_csv_file_rejects_missing_file() {
        let err = read_csv_file(Path::new("C:\\definitely\\missing.csv")).unwrap_err();
        assert!(err.starts_with("csv_read"));
    }

    #[test]
    fn parse_rejects_empty_file() {
        let err = parse_csv("").unwrap_err();
        assert!(err.contains("empty"));
    }

    #[test]
    fn assets_path_guard_rejects_escape_and_absolute() {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir_all(dir.path().join("assets")).unwrap();
        let root = dir.path();
        for bad in ["..\\config\\evil.csv", "C:\\outside.csv", "/abs/path.csv"] {
            let err = resolve_assets_path(root, bad).unwrap_err();
            assert!(err.contains("assets"), "{bad}: {err}");
        }
        let ok = resolve_assets_path(root, "knowledge_base.csv").unwrap();
        assert!(ok.ends_with("knowledge_base.csv"));
    }

    #[test]
    fn run_validator_relays_missing_script_error() {
        let dir = tempfile::tempdir().unwrap();
        let err = run_validator(dir.path(), &dir.path().join("a.csv")).unwrap_err();
        assert!(err.starts_with("validator_missing"));
    }

    #[test]
    fn run_validator_parses_report_json_via_venv_python() {
        let dir = tempfile::tempdir().unwrap();
        let csv_path = dir.path().join("kb.csv");
        fs::write(&csv_path, "topic\nBed Adhesion\n").unwrap();
        let report = r#"{"valid":false,"checkedAt":"2026-01-01T00:00:00Z","errors":[{"row":2,"column":"topic","code":"duplicate_topic","message":"duplicate topic"}],"warnings":[]}"#;
        fs::write(&dir.path().join("report.json"), report).unwrap();

        // Fake .venv python that cats the report (Windows .cmd shim).
        #[cfg(windows)]
        let shim = format!(
            "@echo off\r\ntype \"{}\"\r\n",
            dir.path().join("report.json").display()
        );
        #[cfg(not(windows))]
        let shim = format!("#!/bin/sh\ncat \"{}\"\n", dir.path().join("report.json").display());
        fs::create_dir_all(dir.path().join(".venv").join("Scripts")).unwrap();
        #[cfg(windows)]
        fs::write(
            dir.path().join(".venv").join("Scripts").join("python.cmd"),
            shim,
        )
        .unwrap();
        #[cfg(not(windows))]
        {
            fs::create_dir_all(dir.path().join(".venv").join("bin")).unwrap();
            fs::write(dir.path().join(".venv").join("bin").join("python"), shim).unwrap();
        }

        fs::write(dir.path().join("validate_knowledge_csv.py"), "# fake\n").unwrap();
        let got = run_validator(dir.path(), &csv_path).unwrap();
        assert!(!got.valid);
        assert_eq!(got.errors.len(), 1);
        assert_eq!(got.errors[0].code, "duplicate_topic");
        assert_eq!(got.errors[0].row, 2);
    }

    #[test]
    fn validator_failure_relays_exit_error() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join("kb.csv"), "topic\n").unwrap();
        #[cfg(windows)]
        let shim = "@echo off\r\necho boom >&2\r\nexit /b 3\r\n";
        #[cfg(not(windows))]
        let shim = "#!/bin/sh\necho boom >&2\nexit 3\n";
        fs::create_dir_all(dir.path().join(".venv").join("Scripts")).unwrap();
        #[cfg(windows)]
        fs::write(
            dir.path().join(".venv").join("Scripts").join("python.cmd"),
            shim,
        )
        .unwrap();
        #[cfg(not(windows))]
        {
            fs::create_dir_all(dir.path().join(".venv").join("bin")).unwrap();
            fs::write(dir.path().join(".venv").join("bin").join("python"), shim).unwrap();
        }
        fs::write(dir.path().join("validate_knowledge_csv.py"), "# fake\n").unwrap();
        let err = run_validator(dir.path(), &dir.path().join("kb.csv")).unwrap_err();
        assert!(err.starts_with("validator_exit: code 3"));
    }
}

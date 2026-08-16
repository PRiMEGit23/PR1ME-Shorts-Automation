//! IPC commands — thin, stateless bridges to engine artifacts.

pub mod app;
pub mod csv;
pub mod layout;
pub mod process;
pub mod productions;
pub mod providers;
pub mod runs;
pub mod settings;

use std::fs;
use std::io::Write;
use std::path::Path;

use serde::Serialize;

/// `{ok}` ack for mutating commands (IPC contract, PRODUCT_LAYER §6).
#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct OkPayload {
    pub ok: bool,
}

/// Shared atomic file write (tmp + rename) for every artifact writer.
pub(crate) fn write_bytes_atomic(path: &Path, bytes: &[u8], code: &str) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("{code}: no parent for {}", path.display()))?;
    fs::create_dir_all(parent).map_err(|e| format!("{code}: mkdir {parent:?}: {e}"))?;
    let tmp = parent.join(format!(
        ".{}.{}.tmp",
        path.file_name()
            .map(|f| f.to_string_lossy().to_string())
            .unwrap_or_else(|| "write".to_string()),
        std::process::id()
    ));
    {
        let mut f = fs::File::create(&tmp).map_err(|e| format!("{code}: create tmp: {e}"))?;
        f.write_all(bytes).map_err(|e| format!("{code}: write tmp: {e}"))?;
        f.sync_all().map_err(|e| format!("{code}: sync tmp: {e}"))?;
    }
    if cfg!(windows) && path.exists() {
        fs::remove_file(path).map_err(|e| format!("{code}: replace existing: {e}"))?;
    }
    fs::rename(&tmp, path).map_err(|e| format!("{code}: rename: {e}"))?;
    Ok(())
}
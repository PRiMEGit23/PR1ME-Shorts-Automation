//! Sidecar control of the `pr1me` engine process.
//!
//! Resolution order (IMPLEMENTATION_PLAN 2S1): resources/pr1me.exe →
//! PATH → `<repo_root>/.venv/Scripts/pr1me.exe`. Processes are spawned with
//! CWD = repo_root (the backend resolves `.env` relative to CWD) and
//! injected env; killing the child kills the process tree.

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

/// Engine executable name per platform.
pub fn exe_name() -> &'static str {
    if cfg!(windows) {
        "pr1me.exe"
    } else {
        "pr1me"
    }
}

fn resolve_on_path(name: &str) -> Option<PathBuf> {
    let probes: Vec<String> = if cfg!(windows) {
        // real console shims are .exe; operators may also drop a .cmd shim
        vec![format!("{name}.exe"), format!("{name}.cmd"), format!("{name}.bat")]
    } else {
        vec![name.to_string()]
    };
    let paths = std::env::var_os("PATH")?;
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

/// Resolve the pr1me executable following the documented order.
pub fn resolve_pr1me(repo_root: &Path) -> Option<PathBuf> {
    if let Some(found) = resolve_on_path("pr1me") {
        return Some(found);
    }
    let scripts = repo_root.join(".venv").join("Scripts");
    let mut candidates = vec![
        scripts.join(exe_name()),
        scripts.join("pr1me.cmd"),
        scripts.join("pr1me.bat"),
        repo_root.join(".venv").join("bin").join(exe_name()),
    ];
    if !cfg!(windows) {
        candidates.push(repo_root.join(".venv").join("bin").join("pr1me"));
    }
    candidates.into_iter().find(|c| c.is_file())
}

/// Run `pr1me --version` with a 3s timeout; parse `pr1me 1.0.0`.
pub fn probe_pr1me_version(repo_root: &Path) -> Option<String> {
    let exe = resolve_pr1me(repo_root)?;
    let mut child = Command::new(&exe)
        .arg("--version")
        .current_dir(repo_root)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .ok()?;

    let deadline = Instant::now() + Duration::from_secs(3);
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) => {
                if Instant::now() >= deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    return None;
                }
                std::thread::sleep(Duration::from_millis(25));
            }
            Err(_) => return None,
        }
    };
    if !status.success() {
        return None;
    }
    let mut out = String::new();
    use std::io::Read;
    child
        .stdout
        .take()
        .and_then(|mut o| o.read_to_string(&mut out).ok())
        .map(|_| ())?;

    // Expected format: "pr1me 1.0.0"
    let line = out.lines().next()?.trim();
    let version = line.strip_prefix("pr1me ")?;
    Some(version.to_string())
}

/// A supervised engine process (2S4 uses this to stream runs).
#[allow(dead_code)]
pub struct Pr1meChild {
    child: Child,
    exe: PathBuf,
    repo_root: PathBuf,
}

#[allow(dead_code)]
impl Pr1meChild {
    /// Spawn `pr1me <args>` with CWD = repo_root and the given env overlay.
    pub fn spawn(repo_root: &Path, args: &[String], env: &[(String, String)]) -> Result<Self, String> {
        let exe = resolve_pr1me(repo_root).ok_or_else(|| "pr1me not found on PATH or .venv".to_string())?;
        let mut cmd = Command::new(&exe);
        cmd.args(args)
            .current_dir(repo_root)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        for (key, value) in env {
            cmd.env(key, value);
        }
        let child = cmd.spawn().map_err(|e| format!("spawn {exe:?}: {e}"))?;
        Ok(Self {
            child,
            exe,
            repo_root: repo_root.to_path_buf(),
        })
    }

    pub fn pid(&self) -> u32 {
        self.child.id()
    }

    /// Non-blocking exit check.
    pub fn try_exit(&mut self) -> Option<std::process::ExitStatus> {
        self.child.try_wait().unwrap_or(None)
    }

    /// Blocking exit with timeout; kills on timeout.
    pub fn wait_timeout(&mut self, timeout: Duration) -> Option<std::process::ExitStatus> {
        let deadline = Instant::now() + timeout;
        loop {
            if let Some(status) = self.try_exit() {
                return Some(status);
            }
            if Instant::now() >= deadline {
                let _ = self.kill();
                return None;
            }
            std::thread::sleep(Duration::from_millis(25));
        }
    }

    /// Kill the process tree (Windows: taskkill /T /F).
    pub fn kill(&mut self) -> Result<(), String> {
        let _ = self.child.kill();
        let _ = self.child.wait();
        if cfg!(windows) {
            let _ = Command::new("taskkill")
                .args(["/PID", &self.child.id().to_string(), "/T", "/F"])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
        Ok(())
    }
}

impl Drop for Pr1meChild {
    fn drop(&mut self) {
        let _ = self.kill();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const FAKE: &str = "@echo off\r\necho pr1me 1.0.0\r\n";

    /// Windows fake engines are .cmd shims (a text .exe cannot run).
    fn fake_name() -> &'static str {
        if cfg!(windows) {
            "pr1me.cmd"
        } else {
            "pr1me"
        }
    }

    fn write_fake(dir: &Path) -> PathBuf {
        std::fs::create_dir_all(dir).unwrap();
        let exe = dir.join(fake_name());
        std::fs::write(&exe, FAKE).unwrap();
        exe
    }

    #[test]
    fn resolves_from_path() {
        let dir = tempfile::tempdir().unwrap();
        write_fake(dir.path());
        let old = std::env::var_os("PATH");
        std::env::set_var("PATH", std::env::join_paths([dir.path().to_path_buf()]).unwrap());
        let found = resolve_pr1me(Path::new("C:\\nope"));
        match old {
            Some(v) => std::env::set_var("PATH", v),
            None => std::env::remove_var("PATH"),
        }
        assert!(found.is_some(), "pr1me.cmd on PATH should resolve");
    }

    #[test]
    fn resolves_from_venv_scripts() {
        let dir = tempfile::tempdir().unwrap();
        write_fake(&dir.path().join(".venv").join("Scripts"));
        let old = std::env::var_os("PATH");
        std::env::remove_var("PATH");
        let found = resolve_pr1me(dir.path());
        match old {
            Some(v) => std::env::set_var("PATH", v),
            None => std::env::remove_var("PATH"),
        }
        assert!(found.is_some(), ".venv/Scripts should resolve");
    }

    #[test]
    fn probe_parses_version_from_fake_engine() {
        let dir = tempfile::tempdir().unwrap();
        write_fake(dir.path());
        let old = std::env::var_os("PATH");
        std::env::remove_var("PATH");
        assert_eq!(probe_pr1me_version(dir.path()), None); // not on PATH / venv
        std::env::set_var("PATH", std::env::join_paths([dir.path().to_path_buf()]).unwrap());
        let version = probe_pr1me_version(dir.path());
        match old {
            Some(v) => std::env::set_var("PATH", v),
            None => std::env::remove_var("PATH"),
        }
        assert_eq!(version.as_deref(), Some("1.0.0"));
    }

    #[test]
    fn spawn_injects_env_and_cwd() {
        let dir = tempfile::tempdir().unwrap();
        let exe = dir.path().join("probe.cmd");
        std::fs::write(
            &exe,
            "@echo off\r\necho %CD%\r\necho %PR1ME_TEST_ENV%\r\n",
        )
        .unwrap();
        let mut child = Command::new(&exe)
            .current_dir(dir.path())
            .env("PR1ME_TEST_ENV", "injected")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let status = child.wait().unwrap();
        assert!(status.success());
    }

    #[test]
    fn pr1me_child_kills_on_drop() {
        let dir = tempfile::tempdir().unwrap();
        write_fake(dir.path());
        let old = std::env::var_os("PATH");
        std::env::set_var("PATH", std::env::join_paths([dir.path().to_path_buf()]).unwrap());
        let child = Pr1meChild::spawn(dir.path(), &[], &[]).expect("spawn fake");
        assert!(child.pid() > 0);
        drop(child); // kill-on-drop
        match old {
            Some(v) => std::env::set_var("PATH", v),
            None => std::env::remove_var("PATH"),
        }
    }
}
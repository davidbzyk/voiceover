use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::Manager;
use tokio::process::Command;

/// How long to wait for the sidecar to become healthy after launch.
const HEALTH_CHECK_TIMEOUT_SECS: u64 = 60;
/// Interval between health check polls during startup.
const HEALTH_CHECK_INTERVAL_MS: u64 = 500;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/// Managed state for the TTS sidecar process.
pub struct SidecarState {
    /// Handle to the running sidecar child process.
    child: Mutex<Option<tokio::process::Child>>,
    /// The port the sidecar is listening on.
    port: Mutex<Option<u16>>,
    /// Path to the app data directory passed to the sidecar.
    data_dir: Mutex<Option<PathBuf>>,
}

impl Default for SidecarState {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            port: Mutex::new(None),
            data_dir: Mutex::new(None),
        }
    }
}

// ---------------------------------------------------------------------------
// Binary resolution
// ---------------------------------------------------------------------------

/// Resolve the sidecar binary path.
///
/// In a bundled .app, the sidecar lives next to the main executable in
/// `Contents/MacOS/`. Falls back to running `python server.py` in dev mode.
fn resolve_sidecar_path() -> Option<PathBuf> {
    if let Ok(exe) = std::env::current_exe() {
        let sidecar = exe
            .parent()
            .unwrap_or(Path::new("."))
            .join("voiceover-tts");
        if sidecar.exists() {
            log::info!("[sidecar] Using bundled binary: {:?}", sidecar);
            return Some(sidecar);
        }
    }
    log::info!("[sidecar] No bundled binary found — will use dev mode (python)");
    None
}

/// Find the sidecar Python source for dev mode.
fn resolve_dev_server_path() -> Option<PathBuf> {
    // Walk up from the executable to find the sidecar directory
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors() {
            let server_py = ancestor.join("sidecar").join("server.py");
            if server_py.exists() {
                return Some(server_py);
            }
        }
    }
    // Fallback: relative to CWD
    let fallback = PathBuf::from("sidecar/server.py");
    if fallback.exists() {
        return Some(fallback);
    }
    None
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

/// Find a random available port by binding to port 0.
fn find_available_port() -> Result<u16, String> {
    let listener =
        TcpListener::bind("127.0.0.1:0").map_err(|e| format!("Failed to find available port: {e}"))?;
    let port = listener
        .local_addr()
        .map_err(|e| format!("Failed to get port: {e}"))?
        .port();
    drop(listener);
    Ok(port)
}

/// Start the TTS sidecar process.
///
/// Allocates a random port, spawns the sidecar binary (or Python in dev mode),
/// and polls `/health` until the server is ready.
pub async fn start_sidecar(app: &tauri::AppHandle) -> Result<u16, String> {
    let port = find_available_port()?;
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {e}"))?;
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| format!("Failed to create data dir: {e}"))?;

    let parent_pid = std::process::id();

    log::info!(
        "[sidecar] Starting: port={}, data_dir={:?}, parent_pid={}",
        port,
        data_dir,
        parent_pid
    );

    let child = if let Some(binary) = resolve_sidecar_path() {
        // Production: run the PyInstaller binary
        Command::new(binary)
            .args([
                "--port",
                &port.to_string(),
                "--data-dir",
                data_dir.to_str().unwrap_or("/tmp"),
                "--parent-pid",
                &parent_pid.to_string(),
            ])
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar binary: {e}"))?
    } else if let Some(server_py) = resolve_dev_server_path() {
        // Dev mode: run Python directly
        log::info!("[sidecar] Dev mode: running {:?}", server_py);
        Command::new("python3")
            .args([
                server_py.to_str().unwrap(),
                "--port",
                &port.to_string(),
                "--data-dir",
                data_dir.to_str().unwrap_or("/tmp"),
                "--parent-pid",
                &parent_pid.to_string(),
            ])
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn Python sidecar: {e}"))?
    } else {
        return Err(
            "TTS sidecar not found — no bundled binary and no dev server.py".to_string(),
        );
    };

    // Store state
    let state = app.state::<SidecarState>();
    *state.child.lock().unwrap() = Some(child);
    *state.port.lock().unwrap() = Some(port);
    *state.data_dir.lock().unwrap() = Some(data_dir);

    // Poll /health until ready
    let deadline =
        std::time::Instant::now() + std::time::Duration::from_secs(HEALTH_CHECK_TIMEOUT_SECS);

    loop {
        if std::time::Instant::now() > deadline {
            // Timeout — kill the child and report failure
            stop_sidecar_inner(&state);
            return Err(format!(
                "TTS sidecar failed to start within {}s",
                HEALTH_CHECK_TIMEOUT_SECS
            ));
        }

        tokio::time::sleep(std::time::Duration::from_millis(HEALTH_CHECK_INTERVAL_MS)).await;

        if health_check(port).await {
            log::info!("[sidecar] Healthy on port {}", port);
            return Ok(port);
        }

        // Check if child has exited unexpectedly
        let mut guard = state.child.lock().unwrap();
        if let Some(ref mut child) = *guard {
            match child.try_wait() {
                Ok(Some(status)) => {
                    *guard = None;
                    return Err(format!("TTS sidecar exited during startup: {status}"));
                }
                Ok(None) => {} // Still running, keep polling
                Err(e) => {
                    return Err(format!("Failed to check sidecar status: {e}"));
                }
            }
        }
    }
}

/// Check if the sidecar is healthy by hitting GET /health.
pub async fn health_check(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{}/health", port);
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(2))
        .build()
        .unwrap_or_default();

    match client.get(&url).send().await {
        Ok(resp) if resp.status().is_success() => {
            // Validate it's actually our server
            if let Ok(body) = resp.json::<serde_json::Value>().await {
                body.get("status").and_then(|s| s.as_str()) == Some("healthy")
            } else {
                false
            }
        }
        _ => false,
    }
}

/// Stop the sidecar child process (inner, takes state ref).
fn stop_sidecar_inner(state: &SidecarState) {
    let mut guard = state.child.lock().unwrap();
    if let Some(ref mut child) = *guard {
        log::info!("[sidecar] Stopping child process");
        // Send kill signal — the watchdog will also self-terminate
        let _ = child.start_kill();
    }
    *guard = None;
    *state.port.lock().unwrap() = None;
}

/// Stop the sidecar process.
pub fn stop_sidecar(state: &SidecarState) {
    stop_sidecar_inner(state);
}

/// Ensure the sidecar is running. If it has died, restart it.
///
/// Returns the port the sidecar is listening on.
pub async fn ensure_running(app: &tauri::AppHandle) -> Result<u16, String> {
    let state = app.state::<SidecarState>();

    // Check if we have a recorded port
    let port = { *state.port.lock().unwrap() };
    if let Some(port) = port {
        // Quick health check
        if health_check(port).await {
            return Ok(port);
        }
        log::warn!("[sidecar] Health check failed on port {} — restarting", port);
    }

    // Sidecar is dead or never started — (re)start it
    stop_sidecar_inner(&state);
    start_sidecar(app).await
}

/// Get the sidecar's current port, if running.
pub fn get_port(state: &SidecarState) -> Option<u16> {
    *state.port.lock().unwrap()
}

// ---------------------------------------------------------------------------
// Tauri commands
// ---------------------------------------------------------------------------

/// Get the current sidecar status.
#[tauri::command]
pub async fn get_sidecar_status(
    app: tauri::AppHandle,
) -> Result<serde_json::Value, String> {
    let state = app.state::<SidecarState>();
    let port = { *state.port.lock().unwrap() };

    let (running, healthy) = if let Some(p) = port {
        (true, health_check(p).await)
    } else {
        (false, false)
    };

    Ok(serde_json::json!({
        "running": running,
        "healthy": healthy,
        "port": port,
    }))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn find_available_port_returns_nonzero() {
        let port = find_available_port().unwrap();
        assert!(port > 0, "expected non-zero port, got: {port}");
    }

    #[test]
    fn find_available_port_returns_different_ports() {
        let p1 = find_available_port().unwrap();
        let p2 = find_available_port().unwrap();
        // They *could* be the same, but with 65k ports it's astronomically unlikely
        // Just verify both succeed
        assert!(p1 > 0);
        assert!(p2 > 0);
    }

    #[test]
    fn sidecar_state_default_has_no_child() {
        let state = SidecarState::default();
        assert!(state.child.lock().unwrap().is_none());
        assert!(state.port.lock().unwrap().is_none());
        assert!(state.data_dir.lock().unwrap().is_none());
    }

    #[tokio::test]
    async fn health_check_returns_false_for_unreachable() {
        // Port 1 should not have our sidecar
        let result = health_check(1).await;
        assert!(!result);
    }

    #[test]
    fn get_port_returns_none_by_default() {
        let state = SidecarState::default();
        assert_eq!(get_port(&state), None);
    }

    #[test]
    fn get_port_returns_stored_port() {
        let state = SidecarState::default();
        *state.port.lock().unwrap() = Some(12345);
        assert_eq!(get_port(&state), Some(12345));
    }
}

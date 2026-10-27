use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tauri::Manager;

/// Polling interval while waiting for a sidecar job to finish.
const POLL_INTERVAL_MS: u64 = 500;
/// After its first chunk, a job that reports no new chunk for this long is treated as hung and cancelled.
/// The slowest chunk measured is a Fish S2 Pro phrase: 37.9 s on the 410 s recording (M5 Max, 2026-10-27);
/// CosyVoice chunks take about 2.5 s. 240 s is about 6x that phrase, an estimate of room for the slower
/// Macs with the memory to load Fish. The sidecar bounds each phrase, so a long wait means a hung engine.
const STALL_AFTER_SECS: u64 = 240;

/// Shared HTTP client for all sidecar communication.
/// Registered as Tauri managed state — no default timeout so each call site
/// can use `tokio::time::timeout()` with an appropriate per-request duration.
pub struct HttpClient {
    pub client: reqwest::Client,
}

/// Send an HTTP request with a per-call timeout.
pub(crate) async fn send_with_timeout(
    future: impl std::future::Future<Output = Result<reqwest::Response, reqwest::Error>>,
    timeout_secs: u64,
    context: &str,
) -> Result<reqwest::Response, String> {
    tokio::time::timeout(std::time::Duration::from_secs(timeout_secs), future)
        .await
        .map_err(|_| format!("{context}: timed out after {timeout_secs}s"))?
        .map_err(|e| format!("{context}: {e}"))
}

// ---------------------------------------------------------------------------
// Public types (shared with the frontend via Tauri commands)
// ---------------------------------------------------------------------------

/// A voice profile available on the local TTS sidecar.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LocalVoice {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub language: String,
}

/// Status of a model on the local TTS sidecar.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub model_name: String,
    pub display_name: String,
    #[serde(default)]
    pub category: String,
    #[serde(default)]
    pub recommended: bool,
    #[serde(default)]
    pub downloaded: bool,
    #[serde(default)]
    pub loaded: bool,
    /// The model card's licence id.
    #[serde(default)]
    pub license: Option<String>,
    /// Download size from the Hub, extra repos included.
    #[serde(default)]
    pub size_gb: Option<f64>,
    /// True when the weights may not be used commercially.
    #[serde(default)]
    pub non_commercial: bool,
}

// ---------------------------------------------------------------------------
// Internal types for sidecar API responses
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct GenerateResponse {
    id: String,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Deserialize)]
pub(crate) struct JobProgress {
    pub done: u32,
    pub total: u32,
}

#[derive(Deserialize)]
struct GenerationStatus {
    status: String,
    #[serde(default)]
    error: Option<String>,
    #[serde(default)]
    progress: JobProgress,
}

#[derive(Deserialize)]
pub(crate) struct ModelsResponse {
    pub models: Vec<ModelInfo>,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Validate that a generation ID contains only safe characters (alphanumeric + hyphens).
fn validate_generation_id(id: &str) -> Result<(), String> {
    if !id.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
        return Err(format!("Invalid generation ID format: {}", id));
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Poll-and-download with stall detection and cancel
// ---------------------------------------------------------------------------

/// How long to wait between polls and how long a running job may go without progress.
#[derive(Clone, Copy)]
pub(crate) struct PollTiming {
    pub interval: std::time::Duration,
    pub stall_after: std::time::Duration,
}

impl Default for PollTiming {
    fn default() -> Self {
        Self {
            interval: std::time::Duration::from_millis(POLL_INTERVAL_MS),
            stall_after: std::time::Duration::from_secs(STALL_AFTER_SECS),
        }
    }
}

/// Ask the sidecar to stop a job, retrying a refused request; failures are logged, since the caller is giving up.
///
/// A 404 counts as done: the sidecar no longer has the job.
async fn cancel_generation(client: &reqwest::Client, base_url: &str, generation_id: &str) {
    const ATTEMPTS: u32 = 3;
    let url = format!("{}/generate/{}/cancel", base_url, generation_id);
    for attempt in 1..=ATTEMPTS {
        let failure = match send_with_timeout(client.post(&url).send(), 10, "Cancel request failed").await {
            Ok(resp) if resp.status().is_success() || resp.status() == reqwest::StatusCode::NOT_FOUND => {
                log::info!("[local_tts] Cancelled generation {}", generation_id);
                return;
            }
            Ok(resp) => format!("HTTP {}", resp.status()),
            Err(e) => e,
        };
        log::warn!("[local_tts] Cancel attempt {attempt} for {} failed: {}", generation_id, failure);
        if attempt < ATTEMPTS {
            tokio::time::sleep(std::time::Duration::from_millis(200)).await;
        }
    }
}

/// Poll a sidecar job until it finishes, then download its audio to `output_wav`.
///
/// `on_progress` gets the job's status and chunk counts whenever either changes, from the first poll.
/// Fails only when the job errors, is cancelled, or stops making chunk progress for `timing.stall_after`; never on total length.
pub(crate) async fn poll_and_download(
    client: &reqwest::Client,
    base_url: &str,
    generation_id: &str,
    output_wav: &Path,
    timing: PollTiming,
    on_progress: &(dyn Fn(&str, JobProgress) + Send + Sync),
    is_cancelled: &(dyn Fn() -> bool + Send + Sync),
) -> Result<PathBuf, String> {
    let status_url = format!("{}/generate/{}/status", base_url, generation_id);
    let mut last_seen: Option<(String, JobProgress)> = None;
    let mut last_change = std::time::Instant::now();
    // Set once the sidecar job has ended or been told to stop; any other early exit cancels it,
    // so a job nobody is waiting for never keeps the serial queue busy.
    let mut job_settled = false;

    let waited: Result<(), String> = async {
        loop {
            tokio::time::sleep(timing.interval).await;

            if is_cancelled() {
                cancel_generation(client, base_url, generation_id).await;
                job_settled = true;
                return Err(CANCELLED.to_string());
            }

            let poll_resp = send_with_timeout(
                client.get(&status_url).send(),
                120,
                "Failed to poll generation status",
            )
            .await?;

            if !poll_resp.status().is_success() {
                let body = poll_resp.text().await.unwrap_or_default();
                return Err(format!("Generation status check failed: {body}"));
            }

            let gen_status: GenerationStatus = poll_resp
                .json()
                .await
                .map_err(|e| format!("Failed to parse generation status: {e}"))?;

            let seen = (gen_status.status.clone(), gen_status.progress);
            if last_seen.as_ref() != Some(&seen) {
                on_progress(&gen_status.status, gen_status.progress);
                last_seen = Some(seen);
                last_change = std::time::Instant::now();
            }

            match gen_status.status.as_str() {
                "completed" => {
                    job_settled = true;
                    log::info!("[local_tts] Generation completed: id={}", generation_id);
                    return Ok(());
                }
                "error" => {
                    job_settled = true;
                    let err_msg = gen_status.error.unwrap_or_else(|| "unknown error".to_string());
                    log::error!("[local_tts] Generation failed: id={}, error={}", generation_id, err_msg);
                    return Err(format!("Local voice conversion failed: {err_msg}"));
                }
                "cancelled" => {
                    job_settled = true;
                    return Err(CANCELLED.to_string());
                }
                // Before the first chunk the model may still be downloading; only a stop after progress is a stall.
                "generating"
                    if gen_status.progress.done > 0 && last_change.elapsed() > timing.stall_after =>
                {
                    return Err(format!(
                        "Local voice conversion stopped making progress ({} of {} chunks done, nothing new for {}s)",
                        gen_status.progress.done,
                        gen_status.progress.total,
                        timing.stall_after.as_secs(),
                    ));
                }
                other => log::debug!("[local_tts] Generation status: {} ({})", other, generation_id),
            }
        }
    }
    .await;

    if let Err(e) = waited {
        if !job_settled {
            cancel_generation(client, base_url, generation_id).await;
        }
        return Err(e);
    }

    let audio_url = format!("{}/audio/{}", base_url, generation_id);
    let audio_resp = send_with_timeout(
        client.get(&audio_url).send(),
        120,
        "Failed to download generated audio",
    )
    .await?;

    if !audio_resp.status().is_success() {
        let body = audio_resp.text().await.unwrap_or_default();
        return Err(format!("Audio download failed: {body}"));
    }

    let bytes = audio_resp
        .bytes()
        .await
        .map_err(|e| format!("Failed to read audio response: {e}"))?;

    log::info!("[local_tts] Downloaded audio: {}KB", bytes.len() / 1024);

    std::fs::write(output_wav, &bytes)
        .map_err(|e| format!("Failed to save audio: {e}"))?;

    Ok(output_wav.to_path_buf())
}

/// Error text for a conversion the user (or a newer conversion) cancelled.
use crate::tts_provider::CANCELLED;

// ---------------------------------------------------------------------------
// Voice conversion (speech-to-speech, same contract as ElevenLabs)
// ---------------------------------------------------------------------------

/// Replace the voice in `input_wav` with the profile's, spoken by `engine` (a sidecar registry key), at the video's length.
///
/// A speech-to-speech engine converts the speech; a text-to-speech engine first transcribes it with `whisper_model`.
/// Reports the job's status and chunk progress through `on_progress`, and stops (cancelling the sidecar job) when
/// `is_cancelled` turns true.
#[allow(clippy::too_many_arguments)]
pub async fn voice_convert(
    client: &reqwest::Client,
    port: u16,
    engine: &str,
    profile_id: &str,
    whisper_model: &str,
    input_wav: &Path,
    output_wav: &Path,
    video_duration: Option<f64>,
    on_progress: &(dyn Fn(&str, JobProgress) + Send + Sync),
    is_cancelled: &(dyn Fn() -> bool + Send + Sync),
) -> Result<(), String> {
    let base = format!("http://127.0.0.1:{}", port);
    let start = std::time::Instant::now();

    log::info!(
        "[local_tts] Voice conversion: engine={}, profile={}, input={:?}, port={}",
        engine, profile_id, input_wav, port,
    );

    let input_path_str = input_wav.to_str()
        .ok_or_else(|| "Input audio path contains non-UTF8 characters".to_string())?;
    let body = serde_json::json!({
        "engine": engine,
        "profile_id": profile_id,
        "whisper_model": whisper_model,
        "source_audio_path": input_path_str,
        "original_duration": video_duration.unwrap_or(0.0),
    });

    let response = send_with_timeout(
        client.post(format!("{}/voice-convert", base)).json(&body).send(),
        600,
        "Voice convert request failed",
    )
    .await?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("Voice conversion failed: {body}"));
    }

    let gen_resp: GenerateResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse voice-convert response: {e}"))?;

    let generation_id = gen_resp.id;
    log::info!(
        "[local_tts] Voice conversion submitted: id={}, elapsed={:.1}s",
        generation_id, start.elapsed().as_secs_f32(),
    );

    poll_and_download(
        client,
        &base,
        &generation_id,
        output_wav,
        PollTiming::default(),
        on_progress,
        is_cancelled,
    ).await?;

    log::info!(
        "[local_tts] Voice conversion complete: total_elapsed={:.1}s",
        start.elapsed().as_secs_f32(),
    );

    Ok(())
}

// ---------------------------------------------------------------------------
// Tauri commands (all use managed sidecar)
// ---------------------------------------------------------------------------

/// Check if the TTS sidecar is running and healthy.
#[tauri::command]
pub async fn test_local_connection(app: tauri::AppHandle) -> Result<bool, String> {
    let state = app.state::<crate::sidecar::SidecarState>();
    match crate::sidecar::get_port(&state) {
        Some(p) => Ok(crate::sidecar::health_check(p).await),
        None => Ok(false),
    }
}

/// List voice profiles available on the TTS sidecar.
#[tauri::command]
pub async fn list_local_voices(app: tauri::AppHandle) -> Result<Vec<LocalVoice>, String> {
    let port = crate::sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/profiles", port);
    log::info!("[local_tts] Fetching voice profiles from sidecar port {}", port);

    let http = app.state::<HttpClient>();
    let response = send_with_timeout(
        http.client.get(&url).send(),
        10,
        "Failed to fetch voice profiles",
    )
    .await?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("Failed to list voices: {body}"));
    }

    let voices: Vec<LocalVoice> = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse voice profiles: {e}"))?;

    log::info!("[local_tts] Found {} voice profiles", voices.len());
    Ok(voices)
}

/// Check the download/load status of models on the TTS sidecar.
#[tauri::command]
pub async fn check_model_status(app: tauri::AppHandle) -> Result<Vec<ModelInfo>, String> {
    let port = crate::sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/models/status", port);
    log::info!("[local_tts] Checking model status on sidecar port {}", port);

    let http = app.state::<HttpClient>();
    let response = send_with_timeout(
        http.client.get(&url).send(),
        10,
        "Failed to check model status",
    )
    .await?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("Failed to get model status: {body}"));
    }

    let resp: ModelsResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse model status: {e}"))?;

    log::info!("[local_tts] Model status: {} models", resp.models.len());
    Ok(resp.models)
}

/// Extract audio from a YouTube video via the TTS sidecar.
#[tauri::command]
pub async fn extract_youtube_audio(
    app: tauri::AppHandle,
    url: String,
    start: String,
    duration: u32,
) -> Result<serde_json::Value, String> {
    let port = crate::sidecar::ensure_running(&app).await?;
    let api_url = format!("http://127.0.0.1:{}/extract-youtube", port);
    log::info!("[local_tts] YouTube extraction: {} (start={}, duration={}s)", url, start, duration);

    let http = app.state::<HttpClient>();
    let response = send_with_timeout(
        http.client
            .post(&api_url)
            .json(&serde_json::json!({
                "url": url,
                "start": start,
                "duration": duration,
            }))
            .send(),
        180,
        "YouTube extraction failed",
    )
    .await?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("YouTube extraction failed: {body}"));
    }

    let result: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse extraction result: {e}"))?;

    Ok(result)
}

/// Poll TTS generation status directly (bypasses sidecar_fetch timeout issues).
/// Uses the stored sidecar port WITHOUT a health check — during ML inference the
/// sidecar may be unresponsive to /health but the generation is still running.
/// A health-check here would cause ensure_running to kill and restart the sidecar,
/// destroying the in-progress generation.
#[tauri::command]
pub async fn poll_generation(
    app: tauri::AppHandle,
    generation_id: String,
) -> Result<serde_json::Value, String> {
    let state = app.state::<crate::sidecar::SidecarState>();
    let port = crate::sidecar::get_port(&state)
        .ok_or_else(|| "TTS sidecar is not running".to_string())?;

    validate_generation_id(&generation_id)?;

    let url = format!(
        "http://127.0.0.1:{}/generate/{}/status",
        port, generation_id
    );
    log::info!("[local_tts] poll_generation: {} (port={})", generation_id, port);

    let http = app.state::<HttpClient>();
    let response = send_with_timeout(
        http.client.get(&url).send(),
        120,
        "Failed to poll generation",
    )
    .await
    .map_err(|e| {
        log::warn!("[local_tts] poll_generation request failed: {}", e);
        e
    })?;

    let status = response.status();
    if !status.is_success() {
        let body = response.text().await.unwrap_or_default();
        log::warn!("[local_tts] poll_generation HTTP {}: {}", status, body);
        return Err(format!("Generation status error: {body}"));
    }

    let result: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse generation status: {e}"))?;

    log::info!("[local_tts] poll_generation result: {}", result);
    Ok(result)
}

/// Fetch generated audio bytes from the sidecar.
///
/// Routes audio through Tauri IPC so the webview doesn't need direct HTTP
/// access to the sidecar (eliminates `media-src http://127.0.0.1:*` from CSP).
#[tauri::command]
pub async fn get_generation_audio(
    app: tauri::AppHandle,
    generation_id: String,
) -> Result<Vec<u8>, String> {
    validate_generation_id(&generation_id).map_err(|e| {
        log::warn!("[local_tts] get_generation_audio: {}", e);
        e
    })?;

    let state = app.state::<crate::sidecar::SidecarState>();
    let port = crate::sidecar::get_port(&state).ok_or_else(|| {
        log::warn!("[local_tts] get_generation_audio: sidecar not running");
        "TTS sidecar is not running".to_string()
    })?;

    let url = format!("http://127.0.0.1:{}/audio/{}", port, generation_id);
    let http = app.state::<HttpClient>();
    let response = send_with_timeout(http.client.get(&url).send(), 30, "Failed to fetch audio")
        .await
        .map_err(|e| {
            log::warn!("[local_tts] get_generation_audio: {}", e);
            e
        })?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        log::warn!("[local_tts] get_generation_audio: HTTP error: {body}");
        return Err(format!("Audio fetch failed: {body}"));
    }

    response
        .bytes()
        .await
        .map(|b| b.to_vec())
        .map_err(|e| {
            log::warn!("[local_tts] get_generation_audio: failed to read bytes: {e}");
            format!("Failed to read audio bytes: {e}")
        })
}

/// Permitted sidecar path prefixes — only these endpoints are reachable from the frontend.
const ALLOWED_SIDECAR_PATHS: &[&str] = &[
    "/health",
    "/profiles",
    "/generate",
    "/audio/",
    "/models",
    "/transcribe",
    "/voice-convert",
    "/extract-youtube",
];

/// Proxy a JSON request to the TTS sidecar (for frontend use).
#[tauri::command]
pub async fn sidecar_fetch(
    app: tauri::AppHandle,
    path: String,
    method: String,
    body: Option<String>,
) -> Result<String, String> {
    // Validate path against allowlist to prevent arbitrary endpoint access
    if !ALLOWED_SIDECAR_PATHS.iter().any(|prefix| path.starts_with(prefix)) {
        return Err(format!("Sidecar path not allowed: {}", path));
    }

    let port = crate::sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}{}", port, path);
    log::info!("[local_tts] Sidecar {} {}", method, url);

    // Longer timeout: PyInstaller sidecar can hold the GIL during ML inference,
    // making even simple GET requests wait until the inference step releases it.
    let http = app.state::<HttpClient>();
    let mut req = match method.to_uppercase().as_str() {
        "POST" => http.client.post(&url),
        "PUT" => http.client.put(&url),
        "DELETE" => http.client.delete(&url),
        "GET" => http.client.get(&url),
        _ => return Err(format!("Unsupported HTTP method: {}", method)),
    };

    if let Some(b) = body {
        req = req.header("Content-Type", "application/json").body(b);
    }

    let resp = send_with_timeout(req.send(), 120, "Request failed").await?;
    let status = resp.status();
    let text = resp.text().await.map_err(|e| format!("Failed to read response: {e}"))?;

    if !status.is_success() {
        return Err(format!("{}: {}", status, text));
    }

    Ok(text)
}

/// Permitted upload path prefixes — only these endpoints accept file uploads from the frontend.
const ALLOWED_UPLOAD_PATHS: &[&str] = &["/profiles/"];

/// Upload bytes to the TTS sidecar via multipart form (for sample uploads).
#[tauri::command]
pub async fn sidecar_upload(
    app: tauri::AppHandle,
    path: String,
    file_bytes: Vec<u8>,
    file_name: String,
    file_field: String,
    fields: std::collections::HashMap<String, String>,
) -> Result<String, String> {
    if !ALLOWED_UPLOAD_PATHS.iter().any(|prefix| path.starts_with(prefix)) {
        return Err(format!("Upload path not allowed: {}", path));
    }

    let port = crate::sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}{}", port, path);
    log::info!("[local_tts] Upload to {} (file: {}, {}KB)", url, file_name, file_bytes.len() / 1024);

    let mut form = reqwest::multipart::Form::new()
        .part(
            file_field,
            reqwest::multipart::Part::bytes(file_bytes)
                .file_name(file_name)
                .mime_str("application/octet-stream")
                .map_err(|e| e.to_string())?,
        );

    for (key, value) in fields {
        form = form.text(key, value);
    }

    let http = app.state::<HttpClient>();
    let resp = send_with_timeout(
        http.client.post(&url).multipart(form).send(),
        60,
        "Upload failed",
    )
    .await?;

    let status = resp.status();
    let text = resp.text().await.map_err(|e| format!("Failed to read response: {e}"))?;

    if !status.is_success() {
        return Err(format!("{}: {}", status, text));
    }

    Ok(text)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn local_voice_deserializes_with_defaults() {
        let json = r#"{"id": "prof_1", "name": "Test Voice"}"#;
        let voice: LocalVoice = serde_json::from_str(json).unwrap();
        assert_eq!(voice.id, "prof_1");
        assert_eq!(voice.name, "Test Voice");
        assert!(voice.language.is_empty());
    }

    #[test]
    fn local_voice_deserializes_with_language() {
        let json = r#"{"id": "prof_2", "name": "French Voice", "language": "fr"}"#;
        let voice: LocalVoice = serde_json::from_str(json).unwrap();
        assert_eq!(voice.language, "fr");
    }

    #[test]
    fn model_info_deserializes_with_defaults() {
        let json = r#"{"model_name": "tts-v1", "display_name": "TTS Model v1"}"#;
        let info: ModelInfo = serde_json::from_str(json).unwrap();
        assert_eq!(info.model_name, "tts-v1");
        assert_eq!(info.category, "");
        assert!(!info.recommended);
        assert!(!info.downloaded);
        assert!(!info.loaded);
    }

    #[test]
    fn model_info_deserializes_full() {
        let json = r#"{"model_name": "tts-v1", "display_name": "TTS Model v1", "category": "transcription", "recommended": true, "downloaded": true, "loaded": true}"#;
        let info: ModelInfo = serde_json::from_str(json).unwrap();
        assert_eq!(info.category, "transcription");
        assert!(info.recommended);
        assert!(info.downloaded);
        assert!(info.loaded);
    }

    #[test]
    fn model_info_keeps_the_size_and_licence_the_models_page_shows() {
        // One row of a real /models/status body (2026-10-27).
        let json = r#"{"model_name": "fish-s2-pro", "display_name": "Fish S2 Pro", "category": "tts", "recommended": false, "downloaded": true, "loaded": false, "license": "fish-audio-research", "size_gb": 11.0, "non_commercial": true}"#;
        let info: ModelInfo = serde_json::from_str(json).unwrap();
        let out = serde_json::to_value(&info).unwrap();
        assert_eq!(out["license"], "fish-audio-research");
        assert_eq!(out["size_gb"], 11.0);
        assert_eq!(out["non_commercial"], true);
    }

    #[test]
    fn local_voice_serializes_correctly() {
        let voice = LocalVoice {
            id: "prof_1".to_string(),
            name: "Test".to_string(),
            language: "en".to_string(),
        };
        let json = serde_json::to_string(&voice).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["id"], "prof_1");
        assert_eq!(v["name"], "Test");
        assert_eq!(v["language"], "en");
    }

    /// A scripted stand-in for the sidecar: serves status bodies in order, then audio; records cancel calls
    /// and the body of each job request.
    struct FakeSidecar {
        base_url: String,
        cancels: std::sync::Arc<std::sync::atomic::AtomicUsize>,
        jobs: std::sync::Arc<std::sync::Mutex<Vec<serde_json::Value>>>,
    }

    /// Read one HTTP request: headers, then as many body bytes as Content-Length says.
    async fn read_request(sock: &mut tokio::net::TcpStream) -> String {
        use tokio::io::AsyncReadExt;
        let mut data = Vec::new();
        let mut buf = [0u8; 4096];
        loop {
            let n = sock.read(&mut buf).await.unwrap_or(0);
            if n == 0 {
                break;
            }
            data.extend_from_slice(&buf[..n]);
            let text = String::from_utf8_lossy(&data);
            if let Some(end) = text.find("\r\n\r\n") {
                let length = text[..end]
                    .lines()
                    .find_map(|l| l.to_ascii_lowercase().strip_prefix("content-length:").map(|v| v.trim().to_string()))
                    .and_then(|v| v.parse::<usize>().ok())
                    .unwrap_or(0);
                if data.len() >= end + 4 + length {
                    break;
                }
            }
        }
        String::from_utf8_lossy(&data).to_string()
    }

    async fn fake_sidecar(statuses: Vec<&'static str>) -> FakeSidecar {
        fake_sidecar_with(statuses, 0).await
    }

    /// Like `fake_sidecar`, but the first `failing_cancels` cancel requests answer HTTP 500.
    async fn fake_sidecar_with(statuses: Vec<&'static str>, failing_cancels: usize) -> FakeSidecar {
        use std::sync::atomic::{AtomicUsize, Ordering};
        use std::sync::Arc;
        use tokio::io::AsyncWriteExt;

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let cancels = Arc::new(AtomicUsize::new(0));
        let jobs = Arc::new(std::sync::Mutex::new(Vec::new()));
        let polls = Arc::new(AtomicUsize::new(0));
        let statuses = Arc::new(statuses);
        let (cancels_srv, jobs_srv) = (cancels.clone(), jobs.clone());
        tokio::spawn(async move {
            loop {
                let (mut sock, _) = listener.accept().await.unwrap();
                let (cancels, jobs, polls, statuses) =
                    (cancels_srv.clone(), jobs_srv.clone(), polls.clone(), statuses.clone());
                tokio::spawn(async move {
                    let req = read_request(&mut sock).await;
                    let mut code = "200 OK";
                    let (ctype, body): (&str, Vec<u8>) = if req.starts_with("POST /voice-convert") {
                        let json = req.split("\r\n\r\n").nth(1).unwrap_or("");
                        jobs.lock().unwrap().push(serde_json::from_str(json).unwrap_or_default());
                        ("application/json", br#"{"id":"gen-9"}"#.to_vec())
                    } else if req.contains("/cancel") {
                        if cancels.fetch_add(1, Ordering::SeqCst) < failing_cancels {
                            code = "500 Internal Server Error";
                        }
                        ("application/json", br#"{"status":"generating"}"#.to_vec())
                    } else if req.contains("/status") {
                        let i = polls.fetch_add(1, Ordering::SeqCst).min(statuses.len() - 1);
                        if statuses[i] == "HTTP 500" {
                            code = "500 Internal Server Error";
                        }
                        ("application/json", statuses[i].as_bytes().to_vec())
                    } else {
                        ("audio/wav", b"RIFFfake".to_vec())
                    };
                    let head = format!(
                        "HTTP/1.1 {code}\r\nContent-Type: {ctype}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                        body.len()
                    );
                    sock.write_all(head.as_bytes()).await.ok();
                    sock.write_all(&body).await.ok();
                });
            }
        });
        FakeSidecar { base_url, cancels, jobs }
    }

    fn fast_timing(stall_ms: u64) -> PollTiming {
        PollTiming {
            interval: std::time::Duration::from_millis(5),
            stall_after: std::time::Duration::from_millis(stall_ms),
        }
    }

    fn generating(done: u32) -> &'static str {
        Box::leak(format!(r#"{{"status":"generating","error":null,"progress":{{"done":{done},"total":200}}}}"#).into_boxed_str())
    }

    #[tokio::test]
    async fn long_job_that_keeps_progressing_completes_past_any_total_cap() {
        // 200 chunks at 5ms polls: the job runs far longer than its stall window yet never stalls
        let mut statuses: Vec<&'static str> = (0..=200).map(generating).collect();
        statuses.push(r#"{"status":"completed","error":null,"progress":{"done":200,"total":200}}"#);
        let fake = fake_sidecar(statuses).await;
        let out = std::env::temp_dir().join("vo-test-poll-long.wav");
        let seen = std::sync::Mutex::new(Vec::new());
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-1", &out, fast_timing(200),
            &|_, p| seen.lock().unwrap().push(p.done), &|| false,
        ).await;
        assert!(result.is_ok(), "{result:?}");
        assert_eq!(std::fs::read(&out).unwrap(), b"RIFFfake");
        assert_eq!(seen.lock().unwrap().last(), Some(&200));
        assert_eq!(fake.cancels.load(std::sync::atomic::Ordering::SeqCst), 0);
        std::fs::remove_file(&out).ok();
    }

    #[tokio::test]
    async fn a_new_status_is_reported_before_any_chunk_is_done() {
        // A text-to-speech engine transcribes first: no chunks yet, but the label must move on.
        let fake = fake_sidecar(vec![
            r#"{"status":"loading_model","error":null,"progress":{"done":0,"total":0}}"#,
            r#"{"status":"transcribing","error":null,"progress":{"done":0,"total":0}}"#,
            r#"{"status":"completed","error":null,"progress":{"done":7,"total":7}}"#,
        ])
        .await;
        let out = std::env::temp_dir().join("vo-test-poll-status.wav");
        let seen = std::sync::Mutex::new(Vec::new());
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-7", &out, fast_timing(1_000),
            &|status, p| seen.lock().unwrap().push((status.to_string(), p.done)), &|| false,
        ).await;
        assert!(result.is_ok(), "{result:?}");
        let seen = seen.into_inner().unwrap();
        assert_eq!(
            seen.iter().map(|(s, _)| s.as_str()).collect::<Vec<_>>(),
            ["loading_model", "transcribing", "completed"]
        );
        std::fs::remove_file(&out).ok();
    }

    #[tokio::test]
    async fn voice_convert_asks_the_sidecar_for_the_chosen_engine() {
        let fake = fake_sidecar(vec![r#"{"status":"completed","error":null,"progress":{"done":1,"total":1}}"#]).await;
        let port: u16 = fake.base_url.rsplit(':').next().unwrap().parse().unwrap();
        let out = std::env::temp_dir().join("vo-test-convert-engine.wav");
        voice_convert(
            &reqwest::Client::new(), port, "qwen-tts-1.7B", "4ad88b19", "whisper-large-v3-turbo",
            Path::new("/tmp/extracted-1.wav"), &out, Some(29.993), &|_, _| {}, &|| false,
        )
        .await
        .unwrap();
        let jobs = fake.jobs.lock().unwrap().clone();
        assert_eq!(jobs.len(), 1);
        assert_eq!(jobs[0]["engine"], "qwen-tts-1.7B");
        assert_eq!(jobs[0]["profile_id"], "4ad88b19");
        assert_eq!(jobs[0]["whisper_model"], "whisper-large-v3-turbo");
        assert_eq!(jobs[0]["original_duration"], 29.993);
        std::fs::remove_file(&out).ok();
    }

    #[tokio::test]
    async fn job_with_no_new_chunk_for_the_stall_window_fails_and_is_cancelled() {
        let fake = fake_sidecar(vec![generating(3)]).await;
        let out = std::env::temp_dir().join("vo-test-poll-stall.wav");
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-2", &out, fast_timing(100),
            &|_, _| {}, &|| false,
        ).await;
        let err = result.unwrap_err();
        assert!(err.contains("stopped making progress"), "{err}");
        assert_eq!(fake.cancels.load(std::sync::atomic::Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn a_failed_status_poll_cancels_the_sidecar_job() {
        let fake = fake_sidecar(vec![generating(1), "HTTP 500"]).await;
        let out = std::env::temp_dir().join("vo-test-poll-500.wav");
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-5", &out, fast_timing(10_000),
            &|_, _| {}, &|| false,
        ).await;
        assert!(result.is_err());
        assert_eq!(fake.cancels.load(std::sync::atomic::Ordering::SeqCst), 1, "job must not keep blocking the queue");
    }

    #[tokio::test]
    async fn waiting_on_the_first_chunk_is_not_a_stall() {
        // The first chunk may download a model on first use; only a stop after progress counts as a stall
        let fake = fake_sidecar(vec![generating(0)]).await;
        let out = std::env::temp_dir().join("vo-test-poll-first.wav");
        let calls = std::sync::atomic::AtomicUsize::new(0);
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-6", &out, fast_timing(20),
            &|_, _| {}, &|| calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst) >= 40,
        ).await;
        assert_eq!(result.unwrap_err(), CANCELLED, "should wait for the user, not report a stall");
    }

    #[tokio::test]
    async fn model_loading_is_not_a_stall() {
        let mut statuses = vec![r#"{"status":"loading_model","error":null,"progress":{"done":0,"total":0}}"#; 60];
        statuses.push(r#"{"status":"completed","error":null,"progress":{"done":1,"total":1}}"#);
        let fake = fake_sidecar(statuses).await;
        let out = std::env::temp_dir().join("vo-test-poll-loading.wav");
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-3", &out, fast_timing(50),
            &|_, _| {}, &|| false,
        ).await;
        assert!(result.is_ok(), "{result:?}");
        std::fs::remove_file(&out).ok();
    }

    #[tokio::test]
    async fn a_refused_cancel_is_retried_until_the_sidecar_accepts_it() {
        let fake = fake_sidecar_with(vec![generating(1)], 1).await;
        let out = std::env::temp_dir().join("vo-test-poll-cancel-retry.wav");
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-1", &out, fast_timing(5_000), &|_, _| {}, &|| true,
        ).await;
        assert_eq!(result.unwrap_err(), CANCELLED);
        assert_eq!(fake.cancels.load(std::sync::atomic::Ordering::SeqCst), 2, "a 500 is not a cancel");
    }

    #[tokio::test]
    async fn user_cancel_cancels_the_sidecar_job() {
        let fake = fake_sidecar(vec![generating(1)]).await;
        let out = std::env::temp_dir().join("vo-test-poll-cancel.wav");
        let calls = std::sync::atomic::AtomicUsize::new(0);
        let result = poll_and_download(
            &reqwest::Client::new(), &fake.base_url, "gen-4", &out, fast_timing(10_000),
            &|_, _| {}, &|| calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst) >= 3,
        ).await;
        assert_eq!(result.unwrap_err(), CANCELLED);
        assert_eq!(fake.cancels.load(std::sync::atomic::Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn test_local_connection_returns_false_for_unreachable() {
        // Port 1 should not have our sidecar — use health_check directly
        let result = crate::sidecar::health_check(1).await;
        assert!(!result);
    }

    #[test]
    fn validate_generation_id_accepts_uuid() {
        assert!(validate_generation_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890").is_ok());
    }

    #[test]
    fn validate_generation_id_rejects_path_traversal() {
        assert!(validate_generation_id("../etc/passwd").is_err());
    }

    #[test]
    fn validate_generation_id_rejects_spaces() {
        assert!(validate_generation_id("id with spaces").is_err());
    }

    #[test]
    fn validate_generation_id_rejects_semicolons() {
        assert!(validate_generation_id("id;rm -rf /").is_err());
    }
}

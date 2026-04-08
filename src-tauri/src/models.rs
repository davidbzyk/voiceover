use crate::local_tts::{HttpClient, send_with_timeout};
use crate::sidecar;
use futures_util::StreamExt;
use serde::Serialize;
use tauri::ipc::Channel;
use tauri::Manager;

// ---------------------------------------------------------------------------
// Progress events sent to the frontend during model downloads
// ---------------------------------------------------------------------------

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase", tag = "event", content = "data")]
pub enum ModelDownloadEvent {
    Progress { progress: f32, status: String },
    Complete { model: String },
    Error { message: String },
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/// Recursively walk a directory tree and sum file sizes.
fn dir_size(path: &std::path::Path) -> u64 {
    let mut total = 0u64;
    if let Ok(entries) = std::fs::read_dir(path) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                total += dir_size(&path);
            } else if let Ok(meta) = path.metadata() {
                total += meta.len();
            }
        }
    }
    total
}

// ---------------------------------------------------------------------------
// SSE parsing
// ---------------------------------------------------------------------------

#[derive(Debug, PartialEq)]
enum SseEvent {
    Progress { progress: f32, status: String },
    Error { message: String },
}

fn parse_sse_line(line: &str) -> Option<SseEvent> {
    let data = line.strip_prefix("data: ")?;
    let event: serde_json::Value = serde_json::from_str(data).ok()?;

    let progress = event.get("progress").and_then(|p| p.as_f64()).unwrap_or(0.0) as f32;
    let status = event
        .get("status")
        .and_then(|s| s.as_str())
        .unwrap_or("")
        .to_string();

    if progress < 0.0 {
        let message = event
            .get("error")
            .and_then(|e| e.as_str())
            .unwrap_or("Unknown error")
            .to_string();
        Some(SseEvent::Error { message })
    } else {
        Some(SseEvent::Progress { progress, status })
    }
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

/// Validate that a model name contains only safe characters and no path traversal.
fn validate_model_name(name: &str) -> Result<(), String> {
    if name.is_empty()
        || !name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '.' || c == '_' || c == '/')
    {
        return Err(format!("Invalid model name: {}", name));
    }
    if name.contains("..") {
        return Err(format!("Invalid model name: {}", name));
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Tauri commands
// ---------------------------------------------------------------------------

/// Download a model from HuggingFace via the sidecar.
///
/// Streams progress events to the frontend via a Tauri Channel.
#[tauri::command]
pub async fn download_model(
    app: tauri::AppHandle,
    model: String,
    on_event: Channel<ModelDownloadEvent>,
) -> Result<(), String> {
    validate_model_name(&model)?;
    let port = sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/models/download", port);

    on_event
        .send(ModelDownloadEvent::Progress {
            progress: 0.0,
            status: format!("Starting download of {}...", model),
        })
        .ok();

    let http = app.state::<HttpClient>();
    let response = send_with_timeout(
        http.client.post(&url).json(&serde_json::json!({"model": model})).send(),
        1800,
        "Download request failed",
    )
    .await?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        on_event
            .send(ModelDownloadEvent::Error {
                message: body.clone(),
            })
            .ok();
        return Err(format!("Download failed: {body}"));
    }

    // Stream SSE from sidecar and forward progress to frontend in real-time
    let mut stream = response.bytes_stream();
    let mut buffer = String::new();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| format!("Stream error: {e}"))?;
        buffer.push_str(&String::from_utf8_lossy(&chunk));

        while let Some(newline_pos) = buffer.find('\n') {
            let line = buffer[..newline_pos].to_string();
            buffer = buffer[newline_pos + 1..].to_string();

            if let Some(parsed) = parse_sse_line(&line) {
                match parsed {
                    SseEvent::Progress { progress, status } => {
                        on_event
                            .send(ModelDownloadEvent::Progress { progress, status })
                            .ok();
                    }
                    SseEvent::Error { message } => {
                        on_event
                            .send(ModelDownloadEvent::Error { message: message.clone() })
                            .ok();
                        return Err(message);
                    }
                }
            }
        }
    }

    on_event
        .send(ModelDownloadEvent::Complete {
            model: model.clone(),
        })
        .ok();

    log::info!("[models] Download complete: {}", model);
    Ok(())
}

/// Delete a downloaded model from the HuggingFace cache via the sidecar.
#[tauri::command]
pub async fn delete_model(
    app: tauri::AppHandle,
    model: String,
) -> Result<serde_json::Value, String> {
    validate_model_name(&model)?;
    let port = sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/models/{}", port, model);

    let http = app.state::<HttpClient>();
    let response = send_with_timeout(
        http.client.delete(&url).send(),
        60,
        "Delete request failed",
    )
    .await?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("Model deletion failed: {body}"));
    }

    let result: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse delete response: {e}"))?;

    log::info!("[models] Deleted model: {}", model);
    Ok(result)
}

/// Get the total disk usage of downloaded models.
#[tauri::command]
pub async fn get_models_disk_usage(app: tauri::AppHandle) -> Result<u64, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {e}"))?;
    let models_dir = data_dir.join("models");

    if !models_dir.exists() {
        return Ok(0);
    }

    Ok(dir_size(&models_dir))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn model_download_event_progress_serializes() {
        let event = ModelDownloadEvent::Progress {
            progress: 0.45,
            status: "Downloading...".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["event"], "progress");
        assert_eq!(v["data"]["progress"], 0.45);
    }

    #[test]
    fn model_download_event_complete_serializes() {
        let event = ModelDownloadEvent::Complete {
            model: "whisper".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["event"], "complete");
        assert_eq!(v["data"]["model"], "whisper");
    }

    #[test]
    fn model_download_event_error_serializes() {
        let event = ModelDownloadEvent::Error {
            message: "Network error".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["event"], "error");
        assert_eq!(v["data"]["message"], "Network error");
    }

    // SSE parsing tests (BUG-20)

    #[test]
    fn parse_sse_line_progress() {
        let line = r#"data: {"progress": 0.5, "status": "Downloading model..."}"#;
        let result = parse_sse_line(line);
        assert_eq!(
            result,
            Some(SseEvent::Progress {
                progress: 0.5,
                status: "Downloading model...".to_string(),
            })
        );
    }

    #[test]
    fn parse_sse_line_complete() {
        let line = r#"data: {"progress": 1.0, "status": "Download complete"}"#;
        let result = parse_sse_line(line);
        assert_eq!(
            result,
            Some(SseEvent::Progress {
                progress: 1.0,
                status: "Download complete".to_string(),
            })
        );
    }

    #[test]
    fn parse_sse_line_error() {
        let line = r#"data: {"progress": -1, "status": "Failed", "error": "Disk full"}"#;
        let result = parse_sse_line(line);
        assert_eq!(
            result,
            Some(SseEvent::Error {
                message: "Disk full".to_string(),
            })
        );
    }

    #[test]
    fn parse_sse_line_ignores_non_data() {
        assert_eq!(parse_sse_line(""), None);
        assert_eq!(parse_sse_line("event: message"), None);
        assert_eq!(parse_sse_line(": comment"), None);
    }

    #[test]
    fn parse_sse_line_ignores_malformed_json() {
        assert_eq!(parse_sse_line("data: not-json"), None);
    }

    // validate_model_name tests

    #[test]
    fn validate_model_name_accepts_valid_names() {
        assert!(validate_model_name("whisper-large-v3-turbo").is_ok());
        assert!(validate_model_name("org/model-name").is_ok());
        assert!(validate_model_name("model_v1.0").is_ok());
    }

    #[test]
    fn validate_model_name_rejects_empty() {
        assert!(validate_model_name("").is_err());
    }

    #[test]
    fn validate_model_name_rejects_path_traversal() {
        assert!(validate_model_name("../etc/passwd").is_err());
        assert!(validate_model_name("model/../secret").is_err());
    }

    #[test]
    fn validate_model_name_rejects_special_chars() {
        assert!(validate_model_name("model; rm -rf /").is_err());
        assert!(validate_model_name("model$(cmd)").is_err());
    }

    // dir_size tests (BUG-21)

    #[test]
    fn dir_size_empty_dir() {
        let tmp = std::env::temp_dir().join("voiceover_test_dir_size_empty");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();
        assert_eq!(dir_size(&tmp), 0);
        std::fs::remove_dir_all(&tmp).unwrap();
    }

    #[test]
    fn dir_size_nested_files() {
        let tmp = std::env::temp_dir().join("voiceover_test_dir_size_nested");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(tmp.join("sub")).unwrap();
        std::fs::write(tmp.join("a.txt"), "hello").unwrap(); // 5 bytes
        std::fs::write(tmp.join("sub/b.txt"), "world!").unwrap(); // 6 bytes
        assert_eq!(dir_size(&tmp), 11);
        std::fs::remove_dir_all(&tmp).unwrap();
    }

    #[test]
    fn dir_size_nonexistent() {
        let tmp = std::env::temp_dir().join("voiceover_test_dir_size_nonexist");
        let _ = std::fs::remove_dir_all(&tmp);
        assert_eq!(dir_size(&tmp), 0);
    }
}

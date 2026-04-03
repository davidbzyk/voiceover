use crate::sidecar;
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
// Tauri commands
// ---------------------------------------------------------------------------

/// Check which models are downloaded and/or loaded.
#[tauri::command]
pub async fn check_models_downloaded(
    app: tauri::AppHandle,
) -> Result<Vec<crate::local_tts::ModelInfo>, String> {
    let port = sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/models/status", port);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("Failed to check model status: {e}"))?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("Model status check failed: {body}"));
    }

    let wrapper: crate::local_tts::ModelsResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse model status: {e}"))?;

    Ok(wrapper.models)
}

/// Download a model from HuggingFace via the sidecar.
///
/// Streams progress events to the frontend via a Tauri Channel.
#[tauri::command]
pub async fn download_model(
    app: tauri::AppHandle,
    model: String,
    on_event: Channel<ModelDownloadEvent>,
) -> Result<(), String> {
    let port = sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/models/download", port);

    on_event
        .send(ModelDownloadEvent::Progress {
            progress: 0.0,
            status: format!("Starting download of {}...", model),
        })
        .ok();

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(1800)) // 30 min for large downloads
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .post(&url)
        .json(&serde_json::json!({"model": model}))
        .send()
        .await
        .map_err(|e| format!("Download request failed: {e}"))?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        on_event
            .send(ModelDownloadEvent::Error {
                message: body.clone(),
            })
            .ok();
        return Err(format!("Download failed: {body}"));
    }

    // Read SSE stream from sidecar and forward progress to frontend
    let body = response.text().await.unwrap_or_default();
    for line in body.lines() {
        if let Some(data) = line.strip_prefix("data: ") {
            if let Ok(event) = serde_json::from_str::<serde_json::Value>(data) {
                let progress = event
                    .get("progress")
                    .and_then(|p| p.as_f64())
                    .unwrap_or(0.0) as f32;
                let status = event
                    .get("status")
                    .and_then(|s| s.as_str())
                    .unwrap_or("")
                    .to_string();

                if progress < 0.0 {
                    // Error
                    let err_msg = event
                        .get("error")
                        .and_then(|e| e.as_str())
                        .unwrap_or("Unknown error")
                        .to_string();
                    on_event
                        .send(ModelDownloadEvent::Error { message: err_msg.clone() })
                        .ok();
                    return Err(err_msg);
                }

                on_event
                    .send(ModelDownloadEvent::Progress { progress, status })
                    .ok();
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
    let port = sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/models/{}", port, model);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .delete(&url)
        .send()
        .await
        .map_err(|e| format!("Delete request failed: {e}"))?;

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

    // Walk the directory tree and sum file sizes
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
}

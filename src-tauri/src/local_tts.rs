use serde::{Deserialize, Serialize};
use std::path::Path;

/// Default polling interval when waiting for generation to complete.
const POLL_INTERVAL_MS: u64 = 500;
/// Maximum time to wait for a generation before giving up.
const POLL_TIMEOUT_SECS: u64 = 300;

// ---------------------------------------------------------------------------
// Public types (shared with the frontend via Tauri commands)
// ---------------------------------------------------------------------------

/// A voice profile available on the local Voicebox server.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LocalVoice {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub language: String,
}

/// Status of a model on the local Voicebox server.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub model_name: String,
    pub display_name: String,
    #[serde(default)]
    pub downloaded: bool,
    #[serde(default)]
    pub loaded: bool,
}

// ---------------------------------------------------------------------------
// Internal types for Voicebox API responses
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct SpeechToSpeechResponse {
    id: String,
}

#[derive(Deserialize)]
struct GenerationStatus {
    status: String,
    #[serde(default)]
    error: Option<String>,
}

// ---------------------------------------------------------------------------
// Core speech-to-speech function
// ---------------------------------------------------------------------------

/// Send audio to a local Voicebox server for voice transformation.
///
/// The flow is:
/// 1. POST multipart to `{endpoint}/speech-to-speech` with audio + profile_id
/// 2. Poll `{endpoint}/generate/{id}/status` until completed or failed
/// 3. Download result from `{endpoint}/audio/{id}` and save to `output_wav`
pub async fn speech_to_speech(
    endpoint: &str,
    profile_id: &str,
    input_wav: &Path,
    output_wav: &Path,
) -> Result<(), String> {
    let audio_bytes = std::fs::read(input_wav)
        .map_err(|e| format!("Failed to read input audio: {e}"))?;

    log::info!(
        "[local_tts] S2S request: profile={}, input_size={}KB, endpoint={}",
        profile_id,
        audio_bytes.len() / 1024,
        endpoint,
    );

    let client = reqwest::Client::new();

    // --- Step 1: Submit the speech-to-speech job ---
    let url = format!("{}/speech-to-speech", endpoint.trim_end_matches('/'));
    let form = reqwest::multipart::Form::new()
        .part(
            "audio",
            reqwest::multipart::Part::bytes(audio_bytes)
                .file_name("input.wav")
                .mime_str("audio/wav")
                .map_err(|e| e.to_string())?,
        )
        .text("profile_id", profile_id.to_string());

    let start = std::time::Instant::now();
    let response = client
        .post(&url)
        .multipart(form)
        .send()
        .await
        .map_err(|e| format!("Local TTS request failed: {e}"))?;

    let status = response.status();
    if !status.is_success() {
        let body = response.text().await.unwrap_or_default();
        log::error!("[local_tts] S2S submit error: {status} -- {body}");
        return Err(format!("Local TTS error {status}: {body}"));
    }

    let submit_resp: SpeechToSpeechResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse S2S response: {e}"))?;

    let generation_id = submit_resp.id;
    log::info!(
        "[local_tts] S2S submitted: id={}, elapsed={:.1}s",
        generation_id,
        start.elapsed().as_secs_f32(),
    );

    // --- Step 2: Poll for completion ---
    let status_url = format!(
        "{}/generate/{}/status",
        endpoint.trim_end_matches('/'),
        generation_id,
    );
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(POLL_TIMEOUT_SECS);

    loop {
        if std::time::Instant::now() > deadline {
            return Err(format!(
                "Local TTS timed out after {}s waiting for generation {}",
                POLL_TIMEOUT_SECS, generation_id,
            ));
        }

        tokio::time::sleep(std::time::Duration::from_millis(POLL_INTERVAL_MS)).await;

        let poll_resp = client
            .get(&status_url)
            .send()
            .await
            .map_err(|e| format!("Failed to poll generation status: {e}"))?;

        if !poll_resp.status().is_success() {
            let body = poll_resp.text().await.unwrap_or_default();
            return Err(format!("Generation status check failed: {body}"));
        }

        let gen_status: GenerationStatus = poll_resp
            .json()
            .await
            .map_err(|e| format!("Failed to parse generation status: {e}"))?;

        match gen_status.status.as_str() {
            "completed" => {
                log::info!(
                    "[local_tts] Generation completed: id={}, total_elapsed={:.1}s",
                    generation_id,
                    start.elapsed().as_secs_f32(),
                );
                break;
            }
            "failed" => {
                let err_msg = gen_status.error.unwrap_or_else(|| "unknown error".to_string());
                log::error!("[local_tts] Generation failed: id={}, error={}", generation_id, err_msg);
                return Err(format!("Local TTS generation failed: {err_msg}"));
            }
            other => {
                log::debug!("[local_tts] Generation status: {} ({})", other, generation_id);
            }
        }
    }

    // --- Step 3: Download the result ---
    let audio_url = format!(
        "{}/audio/{}",
        endpoint.trim_end_matches('/'),
        generation_id,
    );
    let audio_resp = client
        .get(&audio_url)
        .send()
        .await
        .map_err(|e| format!("Failed to download generated audio: {e}"))?;

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
        .map_err(|e| format!("Failed to save transformed audio: {e}"))?;

    Ok(())
}

// ---------------------------------------------------------------------------
// Tauri commands
// ---------------------------------------------------------------------------

/// Check if the Voicebox server is reachable.
#[tauri::command]
pub async fn test_local_connection(endpoint: String) -> Result<bool, String> {
    let url = format!("{}/health", endpoint.trim_end_matches('/'));
    log::info!("[local_tts] Testing connection: {}", url);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .map_err(|e| e.to_string())?;

    match client.get(&url).send().await {
        Ok(resp) => {
            let ok = resp.status().is_success();
            if ok {
                log::info!("[local_tts] Connection OK");
            } else {
                log::warn!("[local_tts] Health check returned {}", resp.status());
            }
            Ok(ok)
        }
        Err(e) => {
            log::warn!("[local_tts] Connection failed: {e}");
            Ok(false)
        }
    }
}

/// List voice profiles available on the Voicebox server.
#[tauri::command]
pub async fn list_local_voices(endpoint: String) -> Result<Vec<LocalVoice>, String> {
    let url = format!("{}/profiles", endpoint.trim_end_matches('/'));
    log::info!("[local_tts] Fetching voice profiles from {}", url);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("Failed to fetch voice profiles: {e}"))?;

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

/// Check the download/load status of models on the Voicebox server.
#[tauri::command]
pub async fn check_model_status(endpoint: String) -> Result<Vec<ModelInfo>, String> {
    let url = format!("{}/models/status", endpoint.trim_end_matches('/'));
    log::info!("[local_tts] Checking model status at {}", url);

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
        return Err(format!("Failed to get model status: {body}"));
    }

    let models: Vec<ModelInfo> = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse model status: {e}"))?;

    log::info!("[local_tts] Model status: {} models", models.len());
    Ok(models)
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
        assert!(!info.downloaded);
        assert!(!info.loaded);
    }

    #[test]
    fn model_info_deserializes_full() {
        let json = r#"{"model_name": "tts-v1", "display_name": "TTS Model v1", "downloaded": true, "loaded": true}"#;
        let info: ModelInfo = serde_json::from_str(json).unwrap();
        assert!(info.downloaded);
        assert!(info.loaded);
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

    #[tokio::test]
    async fn test_local_connection_returns_false_for_unreachable() {
        // Port 1 is almost certainly not running a Voicebox server
        let result = test_local_connection("http://127.0.0.1:1".to_string()).await;
        assert_eq!(result.unwrap(), false);
    }
}

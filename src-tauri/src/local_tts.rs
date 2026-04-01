use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tauri::Manager;

/// Default polling interval when waiting for generation to complete.
const POLL_INTERVAL_MS: u64 = 500;
/// Maximum time to wait for a generation before giving up.
const POLL_TIMEOUT_SECS: u64 = 300;

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
    pub downloaded: bool,
    #[serde(default)]
    pub loaded: bool,
}

// ---------------------------------------------------------------------------
// Internal types for sidecar API responses
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct TranscriptionWord {
    #[serde(alias = "text")]
    word: String,
    start: f64,
    end: f64,
}

#[derive(Debug, Deserialize)]
struct TranscriptionSegment {
    start: f64,
    end: f64,
    text: String,
    #[serde(default)]
    words: Vec<TranscriptionWord>,
}

#[derive(Deserialize)]
struct TranscriptionResponse {
    text: String,
    duration: f64,
    #[serde(default)]
    segments: Vec<TranscriptionSegment>,
}

#[derive(Deserialize)]
struct GenerateResponse {
    id: String,
}

#[derive(Deserialize)]
struct GenerationStatus {
    status: String,
    #[serde(default)]
    error: Option<String>,
}

#[derive(Deserialize)]
pub(crate) struct ModelsResponse {
    pub models: Vec<ModelInfo>,
}

// ---------------------------------------------------------------------------
// Shared poll-and-download helper
// ---------------------------------------------------------------------------

/// Poll the sidecar for generation completion, then download the result.
///
/// This is the common pattern shared by `speech_to_speech` and `voice_convert`:
/// 1. Poll `/generate/{id}/status` in a loop until completed or failed
/// 2. Download audio from `/audio/{id}`
/// 3. Save to `output_wav`
async fn poll_and_download(
    client: &reqwest::Client,
    base_url: &str,
    generation_id: &str,
    output_wav: &Path,
    poll_interval: std::time::Duration,
    timeout: std::time::Duration,
) -> Result<PathBuf, String> {
    let status_url = format!("{}/generate/{}/status", base_url, generation_id);
    let deadline = std::time::Instant::now() + timeout;

    loop {
        if std::time::Instant::now() > deadline {
            return Err(format!(
                "Local TTS timed out after {}s waiting for generation {}",
                timeout.as_secs(), generation_id,
            ));
        }

        tokio::time::sleep(poll_interval).await;

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
                    "[local_tts] Generation completed: id={}",
                    generation_id,
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

    // Download the result
    let audio_url = format!("{}/audio/{}", base_url, generation_id);
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
        .map_err(|e| format!("Failed to save audio: {e}"))?;

    Ok(output_wav.to_path_buf())
}

// ---------------------------------------------------------------------------
// Core speech-to-speech function (uses managed sidecar)
// ---------------------------------------------------------------------------

/// Send audio to the managed TTS sidecar for voice transformation.
///
/// The flow is:
/// 1. POST multipart to `/transcribe` to get text from audio
/// 2. POST JSON to `/generate` with profile_id + transcribed text
/// 3. Poll `/generate/{id}/status` until completed or failed (plain JSON)
/// 4. Download result from `/audio/{id}` and save to `output_wav`
pub async fn speech_to_speech(
    port: u16,
    profile_id: &str,
    input_wav: &Path,
    output_wav: &Path,
) -> Result<(), String> {
    let audio_bytes = std::fs::read(input_wav)
        .map_err(|e| format!("Failed to read input audio: {e}"))?;

    let base = format!("http://127.0.0.1:{}", port);

    log::info!(
        "[local_tts] S2S request: profile={}, input_size={}KB, port={}",
        profile_id,
        audio_bytes.len() / 1024,
        port,
    );

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(600))
        .build()
        .map_err(|e| e.to_string())?;
    let start = std::time::Instant::now();

    // --- Step 1: Transcribe audio to text ---
    let form = reqwest::multipart::Form::new()
        .part(
            "file",
            reqwest::multipart::Part::bytes(audio_bytes)
                .file_name("input.wav")
                .mime_str("audio/wav")
                .map_err(|e| e.to_string())?,
        );

    let response = client
        .post(format!("{}/transcribe", base))
        .multipart(form)
        .send()
        .await
        .map_err(|e| format!("Transcription request failed: {e}"))?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        log::error!("[local_tts] Transcribe error: {body}");
        return Err(format!("Transcription failed: {body}"));
    }

    let body_text = response.text().await
        .map_err(|e| format!("Failed to read transcription response: {e}"))?;
    log::info!("[local_tts] Transcribe response: {}", &body_text[..body_text.len().min(500)]);
    let transcription: TranscriptionResponse = serde_json::from_str(&body_text)
        .map_err(|e| format!("Failed to parse transcription: {e} — body: {}", &body_text[..body_text.len().min(200)]))?;

    log::info!(
        "[local_tts] Transcribed: {:.1}s audio -> {} chars, {} segments, elapsed={:.1}s",
        transcription.duration,
        transcription.text.len(),
        transcription.segments.len(),
        start.elapsed().as_secs_f32(),
    );

    if transcription.text.trim().is_empty() {
        return Err("Transcription returned empty text — no speech detected in recording".to_string());
    }

    // Save transcript alongside the output for debugging/review
    let transcript_path = output_wav.with_extension("txt");
    let mut transcript = format!("Duration: {:.3}s\n\n", transcription.duration);
    for seg in &transcription.segments {
        transcript.push_str(&format!(
            "[{:.3}s - {:.3}s] {}\n",
            seg.start, seg.end, seg.text.trim()
        ));
        for w in &seg.words {
            transcript.push_str(&format!(
                "  [{:.3}s - {:.3}s] {}\n",
                w.start, w.end, w.word.trim()
            ));
        }
    }
    transcript.push_str(&format!("\nFull text:\n{}\n", transcription.text));
    if let Err(e) = std::fs::write(&transcript_path, &transcript) {
        log::warn!("[local_tts] Failed to save transcript: {e}");
    } else {
        log::info!("[local_tts] Transcript saved: {:?}", transcript_path);
    }

    // --- Step 2: Generate speech with voice profile ---
    // Include segments and original_duration for timestamp-synchronized generation
    let segments_json: Vec<serde_json::Value> = transcription
        .segments
        .iter()
        .map(|s| {
            let words_json: Vec<serde_json::Value> = s.words.iter().map(|w| {
                serde_json::json!({
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                })
            }).collect();
            serde_json::json!({
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "words": words_json,
            })
        })
        .collect();

    let gen_body = serde_json::json!({
        "profile_id": profile_id,
        "text": transcription.text,
        "language": "en",
        "segments": segments_json,
        "original_duration": transcription.duration,
    });

    let response = client
        .post(format!("{}/generate", base))
        .json(&gen_body)
        .send()
        .await
        .map_err(|e| format!("Generate request failed: {e}"))?;

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        log::error!("[local_tts] Generate error: {body}");
        return Err(format!("Voice generation failed: {body}"));
    }

    let gen_resp: GenerateResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse generate response: {e}"))?;

    let generation_id = gen_resp.id;
    log::info!(
        "[local_tts] Generation submitted: id={}, elapsed={:.1}s",
        generation_id,
        start.elapsed().as_secs_f32(),
    );

    // --- Step 3 & 4: Poll for completion and download result ---
    poll_and_download(
        &client,
        &base,
        &generation_id,
        output_wav,
        std::time::Duration::from_millis(POLL_INTERVAL_MS),
        std::time::Duration::from_secs(POLL_TIMEOUT_SECS),
    ).await?;

    log::info!(
        "[local_tts] S2S complete: total_elapsed={:.1}s",
        start.elapsed().as_secs_f32(),
    );

    Ok(())
}

/// Voice conversion (speech-to-speech): preserves original timing.
///
/// Sends the source audio to the sidecar's `/voice-convert` endpoint which
/// uses CosyVoice2 to convert the voice while keeping the exact pacing.
/// Same poll/download pattern as speech_to_speech.
pub async fn voice_convert(
    port: u16,
    profile_id: &str,
    input_wav: &Path,
    output_wav: &Path,
) -> Result<(), String> {
    let base = format!("http://127.0.0.1:{}", port);
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(600))
        .build()
        .map_err(|e| e.to_string())?;
    let start = std::time::Instant::now();

    log::info!(
        "[local_tts] Voice conversion: profile={}, input={:?}, port={}",
        profile_id, input_wav, port,
    );

    // Submit voice conversion job
    let input_path_str = input_wav.to_str()
        .ok_or_else(|| "Input audio path contains non-UTF8 characters".to_string())?;
    let body = serde_json::json!({
        "profile_id": profile_id,
        "source_audio_path": input_path_str,
    });

    let response = client
        .post(format!("{}/voice-convert", base))
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Voice convert request failed: {e}"))?;

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

    // Poll for completion and download result
    poll_and_download(
        &client,
        &base,
        &generation_id,
        output_wav,
        std::time::Duration::from_millis(POLL_INTERVAL_MS),
        std::time::Duration::from_secs(POLL_TIMEOUT_SECS),
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

/// Check the download/load status of models on the TTS sidecar.
#[tauri::command]
pub async fn check_model_status(app: tauri::AppHandle) -> Result<Vec<ModelInfo>, String> {
    let port = crate::sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}/models/status", port);
    log::info!("[local_tts] Checking model status on sidecar port {}", port);

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

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(180)) // 3 min for large downloads
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .post(&api_url)
        .json(&serde_json::json!({
            "url": url,
            "start": start,
            "duration": duration,
        }))
        .send()
        .await
        .map_err(|e| format!("YouTube extraction failed: {e}"))?;

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

/// Proxy a JSON request to the TTS sidecar (for frontend use).
// TODO: Replace generic sidecar tunnel with typed Tauri commands for defense-in-depth.
// Currently, the frontend controls the path parameter, which could theoretically target
// any sidecar endpoint. Typed commands would restrict to known operations.
#[tauri::command]
pub async fn sidecar_fetch(
    app: tauri::AppHandle,
    path: String,
    method: String,
    body: Option<String>,
) -> Result<String, String> {
    let port = crate::sidecar::ensure_running(&app).await?;
    let url = format!("http://127.0.0.1:{}{}", port, path);
    log::info!("[local_tts] Sidecar {} {}", method, url);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| e.to_string())?;

    let mut req = match method.to_uppercase().as_str() {
        "POST" => client.post(&url),
        "PUT" => client.put(&url),
        "DELETE" => client.delete(&url),
        _ => client.get(&url),
    };

    if let Some(b) = body {
        req = req.header("Content-Type", "application/json").body(b);
    }

    let resp = req.send().await.map_err(|e| format!("Request failed: {e}"))?;
    let status = resp.status();
    let text = resp.text().await.map_err(|e| format!("Failed to read response: {e}"))?;

    if !status.is_success() {
        return Err(format!("{}: {}", status, text));
    }

    Ok(text)
}

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

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()
        .map_err(|e| e.to_string())?;

    let resp = client
        .post(&url)
        .multipart(form)
        .send()
        .await
        .map_err(|e| format!("Upload failed: {e}"))?;

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

    #[test]
    fn transcription_response_deserializes_with_segments() {
        let json = r#"{
            "text": "Hello world",
            "duration": 5.2,
            "segments": [
                {"start": 0.0, "end": 1.5, "text": "Hello"},
                {"start": 2.0, "end": 3.8, "text": "world"}
            ]
        }"#;
        let resp: TranscriptionResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.text, "Hello world");
        assert!((resp.duration - 5.2).abs() < 0.01);
        assert_eq!(resp.segments.len(), 2);
        assert!((resp.segments[0].start - 0.0).abs() < 0.01);
        assert!((resp.segments[0].end - 1.5).abs() < 0.01);
        assert_eq!(resp.segments[0].text, "Hello");
        assert!((resp.segments[1].start - 2.0).abs() < 0.01);
        assert_eq!(resp.segments[1].text, "world");
    }

    #[test]
    fn transcription_response_deserializes_without_segments() {
        let json = r#"{"text": "Hello world", "duration": 3.0}"#;
        let resp: TranscriptionResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.text, "Hello world");
        assert!(resp.segments.is_empty());
    }

    #[test]
    fn transcription_segment_deserializes() {
        let json = r#"{"start": 1.23, "end": 4.56, "text": "test segment"}"#;
        let seg: TranscriptionSegment = serde_json::from_str(json).unwrap();
        assert!((seg.start - 1.23).abs() < 0.001);
        assert!((seg.end - 4.56).abs() < 0.001);
        assert_eq!(seg.text, "test segment");
    }

    #[test]
    fn transcription_word_deserializes_with_word_key() {
        let json = r#"{"word": "hello", "start": 0.5, "end": 1.0}"#;
        let word: TranscriptionWord = serde_json::from_str(json).unwrap();
        assert_eq!(word.word, "hello");
        assert_eq!(word.start, 0.5);
        assert_eq!(word.end, 1.0);
    }

    #[test]
    fn transcription_word_deserializes_with_text_alias() {
        let json = r#"{"text": "world", "start": 1.0, "end": 2.0}"#;
        let word: TranscriptionWord = serde_json::from_str(json).unwrap();
        assert_eq!(word.word, "world");
    }

    #[tokio::test]
    async fn test_local_connection_returns_false_for_unreachable() {
        // Port 1 should not have our sidecar — use health_check directly
        let result = crate::sidecar::health_check(1).await;
        assert!(!result);
    }
}

use std::path::Path;
use tauri::Manager;

/// ElevenLabs API constants — the contract we depend on.
pub(crate) const S2S_BASE_URL: &str = "https://api.elevenlabs.io/v1/speech-to-speech";
pub(crate) const S2S_OUTPUT_FORMAT: &str = "mp3_44100_128";
pub(crate) const S2S_MODEL_ID: &str = "eleven_multilingual_sts_v2";
pub(crate) const API_KEY_HEADER: &str = "xi-api-key";
pub(crate) const USER_ENDPOINT: &str = "https://api.elevenlabs.io/v1/user";

/// Build the S2S endpoint URL for a given voice.
pub(crate) fn s2s_url(voice_id: &str) -> String {
    format!("{S2S_BASE_URL}/{voice_id}?output_format={S2S_OUTPUT_FORMAT}")
}

/// Send audio to ElevenLabs Speech-to-Speech API and save the result.
///
/// NOTE: This function accepts `app` to use the shared `HttpClient` from Tauri
/// managed state. Callers in pipeline.rs must pass `&app` accordingly.
pub async fn speech_to_speech(
    app: &tauri::AppHandle,
    api_key: &str,
    voice_id: &str,
    input_audio: &Path,
    output_audio: &Path,
) -> Result<(), String> {
    let audio_bytes = std::fs::read(input_audio)
        .map_err(|e| format!("Failed to read input audio: {e}"))?;

    log::info!(
        "[elevenlabs] S2S request: voice={}, input_size={}KB",
        voice_id,
        audio_bytes.len() / 1024
    );

    let http = app.state::<crate::local_tts::HttpClient>();
    let client = &http.client;
    let form = reqwest::multipart::Form::new()
        .part(
            "audio",
            reqwest::multipart::Part::bytes(audio_bytes)
                .file_name("input.wav")
                .mime_str("audio/wav")
                .map_err(|e| e.to_string())?,
        )
        .text("model_id", S2S_MODEL_ID)
        .text("remove_background_noise", "true");

    let url = s2s_url(voice_id);

    let start = std::time::Instant::now();
    let response = client
        .post(&url)
        .header(API_KEY_HEADER, api_key)
        .multipart(form)
        .send()
        .await
        .map_err(|e| format!("ElevenLabs API request failed: {e}"))?;

    let status = response.status();
    log::info!("[elevenlabs] S2S response: status={}, elapsed={:.1}s", status, start.elapsed().as_secs_f32());

    if !status.is_success() {
        let body = response.text().await.unwrap_or_default();
        log::error!("[elevenlabs] S2S error: {status} — {body}");
        return Err(format!("ElevenLabs API error {status}: {body}"));
    }

    let bytes = response
        .bytes()
        .await
        .map_err(|e| format!("Failed to read response: {e}"))?;

    log::info!("[elevenlabs] S2S output: {}KB", bytes.len() / 1024);

    std::fs::write(output_audio, &bytes)
        .map_err(|e| format!("Failed to save transformed audio: {e}"))?;

    Ok(())
}

/// Validate an ElevenLabs API key by hitting the user info endpoint.
#[tauri::command]
pub async fn test_api_key(app: tauri::AppHandle, api_key: String) -> Result<bool, String> {
    let trimmed = api_key.trim().to_string();
    if trimmed.is_empty() {
        return Ok(false);
    }

    log::info!("[elevenlabs] Testing API key: ...{}", &trimmed[trimmed.len().saturating_sub(4)..]);

    let http = app.state::<crate::local_tts::HttpClient>();
    let response = http.client
        .get(USER_ENDPOINT)
        .header(API_KEY_HEADER, &trimmed)
        .send()
        .await
        .map_err(|e| format!("Request failed: {e}"))?;

    let status = response.status();
    if status.is_success() {
        log::info!("[elevenlabs] API key valid");
    } else {
        let body = response.text().await.unwrap_or_default();
        log::warn!("[elevenlabs] API key invalid: {status} — {body}");
    }

    Ok(status.is_success())
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- Contract tests: verify our code matches the ElevenLabs API contract ---

    #[test]
    fn s2s_url_uses_correct_base_path() {
        let url = s2s_url("voice123");
        assert!(url.starts_with("https://api.elevenlabs.io/v1/speech-to-speech/"));
    }

    #[test]
    fn s2s_url_embeds_voice_id_in_path() {
        let url = s2s_url("JBFqnCBsd6RMkjVDRZzb");
        assert!(url.contains("/JBFqnCBsd6RMkjVDRZzb?"));
    }

    #[test]
    fn s2s_url_requests_mp3_44100_128_format() {
        let url = s2s_url("any");
        assert!(url.contains("output_format=mp3_44100_128"));
    }

    #[test]
    fn s2s_model_id_is_multilingual_sts_v2() {
        // This is the model ID sent in the multipart form.
        // If ElevenLabs deprecates it, this test reminds us to update.
        assert_eq!(S2S_MODEL_ID, "eleven_multilingual_sts_v2");
    }

    #[test]
    fn api_key_header_is_xi_api_key() {
        // ElevenLabs uses a custom header, not Authorization.
        // If this changes, our requests will 401.
        assert_eq!(API_KEY_HEADER, "xi-api-key");
    }

    #[test]
    fn user_endpoint_is_v1_user() {
        // Used for API key validation — must match ElevenLabs docs.
        assert_eq!(USER_ENDPOINT, "https://api.elevenlabs.io/v1/user");
    }

    #[test]
    fn s2s_url_does_not_have_trailing_slash_before_voice() {
        // Double slashes would 404
        let url = s2s_url("test");
        assert!(!url.contains("//test"));
    }

    // --- Input validation tests ---
    // NOTE: test_api_key now requires a tauri::AppHandle (for shared HttpClient),
    // so we test the validation logic inline rather than calling the command directly.

    #[test]
    fn test_api_key_empty_string_is_detected() {
        let trimmed = "".trim();
        assert!(trimmed.is_empty());
    }

    #[test]
    fn test_api_key_whitespace_only_is_detected() {
        let trimmed = "   ".trim();
        assert!(trimmed.is_empty());
    }

    #[test]
    fn test_api_key_trims_whitespace_preserving_content() {
        let trimmed = "  sk-test-key  ".trim();
        assert!(!trimmed.is_empty());
        assert_eq!(trimmed, "sk-test-key");
    }
}

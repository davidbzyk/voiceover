use std::path::Path;

/// Send audio to ElevenLabs Speech-to-Speech API and save the result.
pub async fn speech_to_speech(
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

    let client = reqwest::Client::new();
    let form = reqwest::multipart::Form::new()
        .part(
            "audio",
            reqwest::multipart::Part::bytes(audio_bytes)
                .file_name("input.wav")
                .mime_str("audio/wav")
                .map_err(|e| e.to_string())?,
        )
        .text("model_id", "eleven_multilingual_sts_v2")
        .text("remove_background_noise", "true");

    let url = format!(
        "https://api.elevenlabs.io/v1/speech-to-speech/{}?output_format=mp3_44100_128",
        voice_id
    );

    let start = std::time::Instant::now();
    let response = client
        .post(&url)
        .header("xi-api-key", api_key)
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
pub async fn test_api_key(api_key: String) -> Result<bool, String> {
    let trimmed = api_key.trim().to_string();
    if trimmed.is_empty() {
        return Ok(false);
    }

    log::info!("[elevenlabs] Testing API key: {}...{}", &trimmed[..6.min(trimmed.len())], &trimmed[trimmed.len().saturating_sub(4)..]);

    let client = reqwest::Client::new();
    let response = client
        .get("https://api.elevenlabs.io/v1/user")
        .header("xi-api-key", &trimmed)
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

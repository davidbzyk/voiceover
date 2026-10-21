use crate::config;
use crate::conversion::{self, ConversionRuns, VoiceChoice};
use crate::ffmpeg;
use crate::library;
use serde::Serialize;
use std::path::{Path, PathBuf};
use tauri::ipc::Channel;
use tauri::Manager;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase", tag = "event", content = "data")]
#[allow(dead_code)]
pub enum PipelineEvent {
    Progress { stage: String, percent: f32 },
    Complete { output_path: String },
    Error { message: String },
}

/// Send a progress event, ignoring a closed channel.
fn progress(on_event: &Channel<PipelineEvent>, stage: &str, percent: f32) {
    on_event
        .send(PipelineEvent::Progress { stage: stage.to_string(), percent })
        .ok();
}

/// Path of the original-voice track kept beside a recording so it can be converted again.
pub(crate) fn original_voice_path(mp4: &Path) -> PathBuf {
    mp4.with_extension("original.m4a")
}

/// Save a new recording as MP4, replacing its voice when `voice_replacement` is on.
#[tauri::command]
pub async fn process_recording(
    app: tauri::AppHandle,
    recording_path: String,
    voice_replacement: bool,
    voice_choice: Option<VoiceChoice>,
    on_event: Channel<PipelineEvent>,
) -> Result<String, String> {
    let recording = PathBuf::from(&recording_path);
    if !recording.exists() {
        return Err("Recording file not found".to_string());
    }

    let rec_meta = std::fs::metadata(&recording);
    log::info!(
        "[pipeline] Starting: voice_replacement={}, input={}, file_size={}KB",
        voice_replacement,
        recording_path,
        rec_meta.as_ref().map(|m| m.len() / 1024).unwrap_or(0),
    );

    let config = config::get_config(app.clone()).await?;
    let output_dir = library::resolve_output_dir(&config.output_dir);
    std::fs::create_dir_all(&output_dir)
        .map_err(|e| format!("Failed to create output directory {:?}: {}", output_dir, e))?;

    let timestamp = unix_timestamp();
    let final_path = output_dir.join(format!("voiceover-{timestamp}.mp4"));
    let pipeline_start = std::time::Instant::now();

    if !voice_replacement {
        progress(&on_event, "Saving", 50.0);
        ffmpeg::normalize_to_mp4(&recording, &final_path).await?;
        update_meta(&final_path, None, None);
        on_event
            .send(PipelineEvent::Complete { output_path: final_path.to_string_lossy().to_string() })
            .ok();
        cleanup_temp(&recording);
        return Ok(final_path.to_string_lossy().to_string());
    }

    // Begun before any work, so a Cancel at any step of this run counts.
    let token = app.state::<ConversionRuns>().begin();
    let choice = conversion::resolve_voice(&config, voice_choice)?;
    let temp_dir = recording.parent().unwrap_or(Path::new("/tmp")).to_path_buf();
    let transformed = convert_voice(&app, &config, &choice, &recording, &recording, &temp_dir, &timestamp, token, &on_event).await?;

    progress(&on_event, "Assembling video", 90.0);
    log::info!("[pipeline] Splicing audio into video");
    let assembled = ffmpeg::replace_audio(&recording, &transformed, &final_path).await;
    cleanup_temp(&transformed);
    assembled?;
    if let Err(e) = ensure_current(&app, token) {
        cleanup_temp(&final_path);
        return Err(e);
    }
    log_duration_drift(&recording, &final_path).await;

    // Keep the speaker's own voice beside the video so it can be converted again later.
    if let Err(e) = ffmpeg::keep_original_voice(&recording, &original_voice_path(&final_path)).await {
        log::warn!("[pipeline] Could not keep original voice: {}", e);
    }

    let name = conversion::voice_name(&app, &config, &choice).await;
    update_meta(&final_path, Some(&choice), name.as_deref());

    log::info!(
        "[pipeline] Complete: {} (total {:.1}s)",
        final_path.display(),
        pipeline_start.elapsed().as_secs_f32()
    );
    on_event
        .send(PipelineEvent::Complete { output_path: final_path.to_string_lossy().to_string() })
        .ok();

    cleanup_temp(&recording);
    tokio::task::spawn_blocking(|| {
        crate::commands::recording::cleanup_stale_recordings(std::time::Duration::from_secs(3600));
    });

    Ok(final_path.to_string_lossy().to_string())
}

/// Convert a saved recording again, from its original voice, into another voice; the mp4 is updated in place.
#[tauri::command]
pub async fn reconvert_recording(
    app: tauri::AppHandle,
    path: String,
    voice_choice: Option<VoiceChoice>,
    on_event: Channel<PipelineEvent>,
) -> Result<String, String> {
    let config = config::get_config(app.clone()).await?;
    let output_dir = library::resolve_output_dir(&config.output_dir);
    let mp4 = PathBuf::from(&path);
    library::validate_in_output_dir(&mp4, &output_dir)?;

    // Begun before any work: a Cancel during the ffmpeg steps below would otherwise be erased by a later begin.
    let token = app.state::<ConversionRuns>().begin();
    let original = original_voice_path(&mp4);
    if !original.exists() {
        if read_meta(&mp4).get("voiceReplacement").and_then(|v| v.as_bool()).unwrap_or(false) {
            return Err(
                "This recording was converted before original voices were kept, so there is no original to convert from"
                    .to_string(),
            );
        }
        // An unconverted recording's own audio is the original voice.
        ffmpeg::keep_original_voice(&mp4, &original).await?;
        ensure_current(&app, token)?;
    }

    let choice = conversion::resolve_voice(&config, voice_choice)?;
    let temp_dir = crate::commands::recording::temp_recording_dir();
    let stamp = unix_timestamp();
    let transformed = convert_voice(&app, &config, &choice, &original, &mp4, &temp_dir, &stamp, token, &on_event).await?;

    progress(&on_event, "Assembling video", 90.0);
    // Staged beside the mp4 so the final rename is atomic: the saved video is never half-written.
    let staged = staging_path(&mp4);
    let swapped = ffmpeg::swap_audio(&mp4, &transformed, &staged).await;
    cleanup_temp(&transformed);
    if let Err(e) = swapped.and_then(|_| ensure_current(&app, token)) {
        cleanup_temp(&staged);
        return Err(e);
    }
    replace_file(&staged, &mp4)?;

    let name = conversion::voice_name(&app, &config, &choice).await;
    update_meta(&mp4, Some(&choice), name.as_deref());
    log::info!("[pipeline] Reconverted {} with {:?}", mp4.display(), choice);
    on_event
        .send(PipelineEvent::Complete { output_path: path.clone() })
        .ok();
    Ok(path)
}

/// Extract `audio_source`'s audio and convert it into `choice`'s voice, reporting progress 5-85%.
///
/// `video` is the file whose length the result must match; `token` is the caller's run. Returns the converted audio's path.
#[allow(clippy::too_many_arguments)]
async fn convert_voice(
    app: &tauri::AppHandle,
    config: &config::AppConfig,
    choice: &VoiceChoice,
    audio_source: &Path,
    video: &Path,
    temp_dir: &Path,
    stamp: &str,
    token: u64,
    on_event: &Channel<PipelineEvent>,
) -> Result<PathBuf, String> {
    let runs = app.state::<ConversionRuns>();

    progress(on_event, "Extracting audio", 5.0);
    // The video is the source of truth for timing: WebM audio can end before the video does.
    let duration = match ffmpeg::probe_duration(video).await {
        Ok(d) => Some(d),
        Err(e) => {
            log::warn!("[pipeline] Could not probe video duration: {} (will use audio duration)", e);
            None
        }
    };
    let extracted = temp_dir.join(format!("extracted-{stamp}.wav"));
    ffmpeg::extract_audio(audio_source, &extracted).await?;
    if let Err(e) = ensure_current(app, token) {
        cleanup_temp(&extracted);
        return Err(e);
    }

    let stage = match choice.provider {
        crate::tts_provider::Provider::Local => "Converting voice (local)",
        crate::tts_provider::Provider::ElevenLabs => "Converting voice (ElevenLabs)",
    };
    progress(on_event, stage, 10.0);
    log::info!("[pipeline] Converting with {:?}, duration={:?}", choice, duration);

    let started = std::time::Instant::now();
    let result = conversion::convert(
        app,
        config,
        choice,
        &extracted,
        temp_dir,
        stamp,
        duration,
        &|fraction| progress(on_event, stage, 10.0 + 75.0 * fraction),
        &|| runs.is_stale(token),
    )
    .await;
    cleanup_temp(&extracted);
    log::info!("[pipeline] Conversion took {:.1}s", started.elapsed().as_secs_f32());
    let converted = result?;
    // A provider that cannot be interrupted mid-request may finish after Cancel; drop its result.
    if let Err(e) = ensure_current(app, token) {
        cleanup_temp(&converted);
        return Err(e);
    }
    progress(on_event, stage, 85.0);
    Ok(converted)
}

/// Fail with the cancelled error when `token`'s run was cancelled or superseded.
fn ensure_current(app: &tauri::AppHandle, token: u64) -> Result<(), String> {
    if app.state::<ConversionRuns>().is_stale(token) {
        return Err(crate::local_tts::CANCELLED.to_string());
    }
    Ok(())
}

/// Where a recording's replacement is written before it is renamed over the original.
fn staging_path(mp4: &Path) -> PathBuf {
    mp4.with_extension("mp4.part")
}

/// Move `staged` over `target` in one rename, so `target` is always either the old or the new file.
fn replace_file(staged: &Path, target: &Path) -> Result<(), String> {
    std::fs::rename(staged, target).map_err(|e| {
        cleanup_temp(staged);
        format!("Failed to update recording: {e}")
    })
}

/// Log a warning when the output's length drifts from the input video's.
async fn log_duration_drift(input: &Path, output: &Path) {
    if let (Ok(input_dur), Ok(output_dur)) = (ffmpeg::probe_duration(input).await, ffmpeg::probe_duration(output).await) {
        log::info!("[pipeline] Output duration: {:.1}s (input video: {:.1}s)", output_dur, input_dur);
        if (output_dur - input_dur).abs() > 1.0 {
            log::warn!("[pipeline] Duration drift: output={:.1}s vs input={:.1}s — possible A/V sync issue", output_dur, input_dur);
        }
    }
}

fn cleanup_temp(path: &Path) {
    std::fs::remove_file(path).ok();
}

/// Read a recording's .meta.json as a JSON object (empty when missing or unreadable).
fn read_meta(output_path: &Path) -> serde_json::Map<String, serde_json::Value> {
    std::fs::read_to_string(output_path.with_extension("meta.json"))
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v.as_object().cloned())
        .unwrap_or_default()
}

/// Record which voice a recording now uses, keeping other fields (Drive link, creation time).
/// `voice_name` should be the resolved human-readable name, not an opaque ID.
fn update_meta(output_path: &Path, choice: Option<&VoiceChoice>, voice_name: Option<&str>) {
    let mut meta = read_meta(output_path);
    meta.insert("voiceProfile".into(), serde_json::json!(voice_name));
    meta.insert("provider".into(), serde_json::json!(choice.map(|c| &c.provider)));
    meta.insert("voiceReplacement".into(), serde_json::json!(choice.is_some()));
    meta.entry("createdAt")
        .or_insert_with(|| serde_json::json!(unix_timestamp().parse::<u64>().unwrap_or(0)));

    let meta_path = output_path.with_extension("meta.json");
    match serde_json::to_string_pretty(&meta) {
        Ok(json) => {
            if let Err(e) = std::fs::write(&meta_path, json) {
                log::warn!("[pipeline] Failed to write meta.json: {}", e);
            } else {
                log::info!("[pipeline] Wrote metadata: {:?}", meta_path);
            }
        }
        Err(e) => log::warn!("[pipeline] Failed to serialize meta.json: {}", e),
    }
}

pub(crate) fn unix_timestamp() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    format!("{secs}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unix_timestamp_returns_numeric_string() {
        let ts = unix_timestamp();
        assert!(ts.chars().all(|c| c.is_ascii_digit()), "expected all digits, got: {ts}");
        let val: u64 = ts.parse().expect("should parse as u64");
        assert!(val > 1_577_836_800, "expected timestamp after year 2020, got: {val}");
    }

    #[test]
    fn pipeline_event_progress_serializes_with_tag() {
        let event = PipelineEvent::Progress {
            stage: "Extracting audio".to_string(),
            percent: 42.5,
        };
        let json = serde_json::to_string(&event).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["event"], "progress");
        let data = &v["data"];
        assert_eq!(data["stage"], "Extracting audio");
        assert_eq!(data["percent"], 42.5);
    }

    #[test]
    fn pipeline_event_complete_serializes_with_output_path() {
        let event = PipelineEvent::Complete {
            output_path: "/tmp/output.mp4".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["event"], "complete");
        // rename_all="camelCase" turns output_path into outputPath
        let data = &v["data"];
        let output = data.get("outputPath").or_else(|| data.get("output_path"));
        assert_eq!(
            output.and_then(|val| val.as_str()),
            Some("/tmp/output.mp4"),
            "actual JSON: {json}"
        );
    }

    #[test]
    fn pipeline_event_error_serializes_with_message() {
        let event = PipelineEvent::Error {
            message: "Something went wrong".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["event"], "error");
        assert_eq!(v["data"]["message"], "Something went wrong");
    }

    fn temp_mp4(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("vo-test-{name}"));
        std::fs::create_dir_all(&dir).ok();
        let mp4 = dir.join("voiceover-1740000000.mp4");
        std::fs::write(&mp4, b"fake").ok();
        mp4
    }

    #[test]
    fn update_meta_records_unconverted_recording() {
        let mp4 = temp_mp4("meta-raw");
        update_meta(&mp4, None, None);
        let v = serde_json::Value::Object(read_meta(&mp4));
        assert_eq!(v["voiceReplacement"], false);
        assert!(v["voiceProfile"].is_null());
        assert!(v["createdAt"].as_u64().unwrap() > 0);
        std::fs::remove_dir_all(mp4.parent().unwrap()).ok();
    }

    #[test]
    fn update_meta_stores_voice_name_and_provider() {
        let mp4 = temp_mp4("meta-local");
        let choice = VoiceChoice { provider: crate::tts_provider::Provider::Local, voice_id: "4ad88b19".into() };
        update_meta(&mp4, Some(&choice), Some("MJ"));
        let v = serde_json::Value::Object(read_meta(&mp4));
        assert_eq!(v["voiceReplacement"], true);
        assert_eq!(v["voiceProfile"], "MJ", "should store human-readable name, not UUID");
        assert_eq!(v["provider"], "local");
        std::fs::remove_dir_all(mp4.parent().unwrap()).ok();
    }

    #[test]
    fn converting_again_keeps_drive_link_and_creation_time() {
        let mp4 = temp_mp4("meta-reconvert");
        std::fs::write(
            mp4.with_extension("meta.json"),
            r#"{"voiceProfile":"MJ","provider":"local","voiceReplacement":true,"createdAt":1740000000,"driveUrl":"https://drive/x","uploadedAt":1740000100}"#,
        ).unwrap();
        let choice = VoiceChoice { provider: crate::tts_provider::Provider::ElevenLabs, voice_id: "el".into() };
        update_meta(&mp4, Some(&choice), Some("Rachel"));
        let v = serde_json::Value::Object(read_meta(&mp4));
        assert_eq!(v["voiceProfile"], "Rachel");
        assert_eq!(v["provider"], "elevenlabs");
        assert_eq!(v["driveUrl"], "https://drive/x");
        assert_eq!(v["createdAt"], 1740000000);
        std::fs::remove_dir_all(mp4.parent().unwrap()).ok();
    }

    #[test]
    fn staging_file_is_beside_the_mp4_and_not_listed_as_a_recording() {
        let staged = staging_path(Path::new("/m/voiceover-1.mp4"));
        assert_eq!(staged.parent(), Some(Path::new("/m")));
        assert_ne!(staged.extension().and_then(|e| e.to_str()), Some("mp4"));
    }

    #[test]
    fn replace_file_swaps_content_and_leaves_no_staging_file() {
        let mp4 = temp_mp4("replace-file");
        let staged = staging_path(&mp4);
        std::fs::write(&staged, b"new video").unwrap();
        replace_file(&staged, &mp4).unwrap();
        assert_eq!(std::fs::read(&mp4).unwrap(), b"new video");
        assert!(!staged.exists());
        std::fs::remove_dir_all(mp4.parent().unwrap()).ok();
    }

    #[test]
    fn original_voice_sits_beside_the_mp4() {
        assert_eq!(
            original_voice_path(Path::new("/m/voiceover-1.mp4")),
            PathBuf::from("/m/voiceover-1.original.m4a")
        );
    }
}

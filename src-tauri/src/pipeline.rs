use crate::config;
use crate::elevenlabs;
use crate::ffmpeg;
use crate::local_tts;
use crate::sidecar;
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

#[tauri::command]
pub async fn process_recording(
    app: tauri::AppHandle,
    recording_path: String,
    voice_replacement: bool,
    voice_id: Option<String>,
    on_event: Channel<PipelineEvent>,
) -> Result<String, String> {
    let recording = PathBuf::from(&recording_path);
    if !recording.exists() {
        return Err("Recording file not found".to_string());
    }

    // Log recording file details for debugging
    let rec_meta = std::fs::metadata(&recording);
    log::info!(
        "[pipeline] Starting: voice_replacement={}, input={}, file_size={}KB",
        voice_replacement,
        recording_path,
        rec_meta.as_ref().map(|m| m.len() / 1024).unwrap_or(0),
    );

    let config = config::get_config(app.clone()).await?;
    let output_dir = crate::library::resolve_output_dir(&config.output_dir);
    std::fs::create_dir_all(&output_dir)
        .map_err(|e| format!("Failed to create output directory {:?}: {}", output_dir, e))?;

    let timestamp = unix_timestamp();
    let final_name = format!("voiceover-{timestamp}.mp4");
    let final_path = output_dir.join(&final_name);
    let pipeline_start = std::time::Instant::now();

    if !voice_replacement {
        // Just normalize to MP4 and save
        on_event
            .send(PipelineEvent::Progress {
                stage: "Saving".to_string(),
                percent: 50.0,
            })
            .ok();

        ffmpeg::normalize_to_mp4(&recording, &final_path).await?;
        write_meta(&final_path, &config, false, None);

        on_event
            .send(PipelineEvent::Complete {
                output_path: final_path.to_string_lossy().to_string(),
            })
            .ok();

        cleanup_temp(&recording);
        return Ok(final_path.to_string_lossy().to_string());
    }

    // Voice replacement pipeline
    let use_local = config.provider == crate::tts_provider::Provider::Local;

    if !use_local {
        let api_key = &config.elevenlabs_api_key;
        if api_key.is_empty() {
            return Err("ElevenLabs API key not set — configure in Settings".to_string());
        }
    }

    let voice_id = voice_id
        .filter(|id| !id.is_empty())
        .or_else(|| {
            config.voices.iter()
                .find(|v| v.is_default)
                .or_else(|| config.voices.first())
                .map(|v| v.id.clone())
        });

    if !use_local && voice_id.is_none() {
        return Err("No voice configured — add one in Settings".to_string());
    }

    if use_local && config.local_voice_profile_id.is_empty() {
        return Err("No local voice profile configured — select one in Settings".to_string());
    }

    let temp_dir = recording.parent().unwrap_or(std::path::Path::new("/tmp"));
    let extracted_wav = temp_dir.join(format!("extracted-{timestamp}.wav"));
    // ElevenLabs outputs MP3; local TTS sidecar outputs WAV.
    // ffmpeg's replace_audio handles both (transcodes to AAC).
    let transformed_audio = if use_local {
        temp_dir.join(format!("transformed-{timestamp}.wav"))
    } else {
        temp_dir.join(format!("transformed-{timestamp}.mp3"))
    };

    // Stage 1: Extract audio (0-10%)
    on_event
        .send(PipelineEvent::Progress {
            stage: "Extracting audio".to_string(),
            percent: 5.0,
        })
        .ok();

    // Probe video duration before extraction — the video is the source of truth for timing.
    // Audio tracks in WebM can be shorter than video (WebRTC records them independently).
    let video_duration = match ffmpeg::probe_duration(&recording).await {
        Ok(dur) => {
            log::info!("[pipeline] Video duration: {:.1}s", dur);
            Some(dur)
        }
        Err(e) => {
            log::warn!("[pipeline] Could not probe video duration: {} (will use audio duration)", e);
            None
        }
    };

    log::info!("[pipeline] Extracting audio to {:?}", extracted_wav);
    ffmpeg::extract_audio(&recording, &extracted_wav).await?;
    let wav_size = std::fs::metadata(&extracted_wav).map(|m| m.len()).unwrap_or(0);
    // 16kHz mono 16-bit = 32000 bytes/sec
    let wav_duration_est = wav_size as f64 / 32000.0;
    log::info!(
        "[pipeline] Audio extracted: {}KB (~{:.1}s)",
        wav_size / 1024,
        wav_duration_est,
    );

    on_event
        .send(PipelineEvent::Progress {
            stage: "Extracting audio".to_string(),
            percent: 10.0,
        })
        .ok();

    // Stage 2: Voice transformation (10-85%)
    // Track the resolved voice name for metadata (human-readable, not opaque ID)
    let resolved_voice_name: Option<String>;

    if use_local {
        on_event
            .send(PipelineEvent::Progress {
                stage: "Transforming voice (local)...".to_string(),
                percent: 15.0,
            })
            .ok();

        let port = sidecar::ensure_running(&app).await?;
        let http = app.state::<local_tts::HttpClient>();
        if config.local_tts_mode == config::LocalTtsMode::Vc {
            log::info!("[pipeline] Using voice conversion (CosyVoice S2S)");
            local_tts::voice_convert(
                &http.client,
                port,
                &config.local_voice_profile_id,
                &extracted_wav,
                &transformed_audio,
                video_duration,
            ).await?;
        } else {
            log::info!("[pipeline] Using text-to-speech (Qwen TTS)");
            local_tts::speech_to_speech(
                &http.client,
                port,
                &config.local_voice_profile_id,
                &extracted_wav,
                &transformed_audio,
                video_duration,
                Some(&config.whisper_model),
            ).await?;
        }

        // Resolve local voice profile ID → human-readable name from sidecar
        resolved_voice_name = match local_tts::list_local_voices(app.clone()).await {
            Ok(voices) => voices.iter()
                .find(|v| v.id == config.local_voice_profile_id)
                .map(|v| v.name.clone()),
            Err(e) => {
                log::warn!("[pipeline] Could not resolve local voice name: {}", e);
                None
            }
        };
    } else {
        on_event
            .send(PipelineEvent::Progress {
                stage: "Transforming voice (ElevenLabs)...".to_string(),
                percent: 15.0,
            })
            .ok();

        elevenlabs::speech_to_speech(
            &app,
            &config.elevenlabs_api_key,
            voice_id.as_deref().ok_or_else(|| "ElevenLabs voice ID is required but not configured".to_string())?,
            &extracted_wav,
            &transformed_audio,
        ).await?;

        // Resolve ElevenLabs voice name from config
        resolved_voice_name = config.voices.iter()
            .find(|v| v.is_default)
            .or_else(|| config.voices.first())
            .map(|v| v.name.clone());
    }

    on_event
        .send(PipelineEvent::Progress {
            stage: "Transforming voice".to_string(),
            percent: 85.0,
        })
        .ok();

    // Stage 3: Splice audio (85-100%)
    on_event
        .send(PipelineEvent::Progress {
            stage: "Assembling video".to_string(),
            percent: 90.0,
        })
        .ok();

    log::info!("[pipeline] Splicing audio into video");
    ffmpeg::replace_audio(&recording, &transformed_audio, &final_path).await?;

    // Diagnostic: compare input vs output durations to detect A/V sync issues
    match ffmpeg::probe_duration(&final_path).await {
        Ok(output_dur) => {
            log::info!(
                "[pipeline] Output duration: {:.1}s (input video: {:.1}s)",
                output_dur,
                video_duration.unwrap_or(0.0),
            );
            if let Some(vid_dur) = video_duration {
                let drift = (output_dur - vid_dur).abs();
                if drift > 1.0 {
                    log::warn!(
                        "[pipeline] Duration drift: output={:.1}s vs input={:.1}s (drift={:.1}s) — possible A/V sync issue!",
                        output_dur, vid_dur, drift,
                    );
                }
            }
        }
        Err(e) => log::warn!("[pipeline] Could not probe output duration: {}", e),
    }

    // Copy transcript alongside the final video (if local TTS generated one)
    if use_local {
        let transcript_src = transformed_audio.with_extension("txt");
        if transcript_src.exists() {
            let transcript_dst = final_path.with_extension("txt");
            match std::fs::copy(&transcript_src, &transcript_dst) {
                Ok(_) => log::info!("[pipeline] Transcript saved: {:?}", transcript_dst),
                Err(e) => log::warn!("[pipeline] Failed to copy transcript: {}", e),
            }
        }
    }

    write_meta(&final_path, &config, true, resolved_voice_name.as_deref());

    log::info!(
        "[pipeline] Complete: {} (total {:.1}s)",
        final_path.display(),
        pipeline_start.elapsed().as_secs_f32()
    );

    on_event
        .send(PipelineEvent::Complete {
            output_path: final_path.to_string_lossy().to_string(),
        })
        .ok();

    // Cleanup temp files from this pipeline run
    cleanup_temp(&recording);
    cleanup_temp(&extracted_wav);
    cleanup_temp(&transformed_audio);
    cleanup_temp(&transformed_audio.with_extension("txt"));

    // Sweep stale artifacts from previous runs (>1 hour old)
    tokio::task::spawn_blocking(|| {
        crate::commands::recording::cleanup_stale_recordings(
            std::time::Duration::from_secs(3600),
        );
    });

    Ok(final_path.to_string_lossy().to_string())
}

fn cleanup_temp(path: &Path) {
    std::fs::remove_file(path).ok();
}

/// Write a .meta.json sidecar alongside the output MP4.
/// `voice_name` should be the resolved human-readable name, not an opaque ID.
fn write_meta(output_path: &Path, config: &config::AppConfig, voice_replacement: bool, voice_name: Option<&str>) {
    let voice_profile = if voice_replacement { voice_name } else { None };

    let meta = serde_json::json!({
        "voiceProfile": voice_profile,
        "provider": if voice_replacement { Some(&config.provider) } else { None },
        "voiceReplacement": voice_replacement,
        "createdAt": unix_timestamp().parse::<u64>().unwrap_or(0),
    });

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

    #[test]
    fn write_meta_creates_sidecar_file() {
        let tmp = std::env::temp_dir().join("vo-test-write-meta");
        std::fs::create_dir_all(&tmp).ok();
        let mp4 = tmp.join("voiceover-1740000000.mp4");
        std::fs::write(&mp4, b"fake").ok();

        let config = config::AppConfig::default();
        write_meta(&mp4, &config, false, None);

        let meta_path = mp4.with_extension("meta.json");
        assert!(meta_path.exists(), "meta.json should be created");

        let content = std::fs::read_to_string(&meta_path).unwrap();
        let v: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(v["voiceReplacement"], false);
        assert!(v["voiceProfile"].is_null());

        // Cleanup
        std::fs::remove_file(&mp4).ok();
        std::fs::remove_file(&meta_path).ok();
        std::fs::remove_dir(&tmp).ok();
    }

    #[test]
    fn write_meta_includes_voice_profile_when_replacement() {
        let tmp = std::env::temp_dir().join("vo-test-write-meta-vr");
        std::fs::create_dir_all(&tmp).ok();
        let mp4 = tmp.join("voiceover-1740000001.mp4");
        std::fs::write(&mp4, b"fake").ok();

        let mut config = config::AppConfig::default();
        config.provider = crate::tts_provider::Provider::ElevenLabs;
        config.voices = vec![config::Voice {
            id: "voice123".to_string(),
            name: "TestVoice".to_string(),
            description: "".to_string(),
            is_default: true,
        }];
        write_meta(&mp4, &config, true, Some("TestVoice"));

        let meta_path = mp4.with_extension("meta.json");
        let content = std::fs::read_to_string(&meta_path).unwrap();
        let v: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(v["voiceReplacement"], true);
        assert_eq!(v["voiceProfile"], "TestVoice");
        assert_eq!(v["provider"], "elevenlabs");

        // Cleanup
        std::fs::remove_file(&mp4).ok();
        std::fs::remove_file(&meta_path).ok();
        std::fs::remove_dir(&tmp).ok();
    }

    #[test]
    fn write_meta_stores_local_voice_name_not_id() {
        let tmp = std::env::temp_dir().join("vo-test-write-meta-local");
        std::fs::create_dir_all(&tmp).ok();
        let mp4 = tmp.join("voiceover-1740000002.mp4");
        std::fs::write(&mp4, b"fake").ok();

        let mut config = config::AppConfig::default();
        config.provider = crate::tts_provider::Provider::Local;
        config.local_voice_profile_id = "4ad88b19-3bfe-493d-8xxx".to_string();
        // Pass the resolved name, not the ID
        write_meta(&mp4, &config, true, Some("MJ"));

        let meta_path = mp4.with_extension("meta.json");
        let content = std::fs::read_to_string(&meta_path).unwrap();
        let v: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(v["voiceReplacement"], true);
        assert_eq!(v["voiceProfile"], "MJ", "should store human-readable name, not UUID");
        assert_eq!(v["provider"], "local");

        std::fs::remove_file(&mp4).ok();
        std::fs::remove_file(&meta_path).ok();
        std::fs::remove_dir(&tmp).ok();
    }
}

use crate::config;
use crate::elevenlabs;
use crate::ffmpeg;
use crate::local_tts;
use crate::sidecar;
use serde::Serialize;
use std::path::{Path, PathBuf};
use tauri::ipc::Channel;

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
    let output_dir = PathBuf::from(&config.output_dir);

    // Fall back to default output dir if configured path can't be created
    let output_dir = match std::fs::create_dir_all(&output_dir) {
        Ok(_) => output_dir,
        Err(e) => {
            log::warn!("[pipeline] Can't create output dir {:?}: {}, using default", output_dir, e);
            let fallback = dirs::video_dir()
                .or_else(dirs::home_dir)
                .map(|p| p.join("VoiceOver"))
                .unwrap_or_else(|| PathBuf::from("/tmp/VoiceOver"));
            std::fs::create_dir_all(&fallback).map_err(|e| e.to_string())?;
            fallback
        }
    };

    let timestamp = chrono_timestamp();
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

        on_event
            .send(PipelineEvent::Complete {
                output_path: final_path.to_string_lossy().to_string(),
            })
            .ok();

        cleanup_temp(&recording);
        return Ok(final_path.to_string_lossy().to_string());
    }

    // Voice replacement pipeline
    let use_local = config.provider == "local";

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
    if use_local {
        on_event
            .send(PipelineEvent::Progress {
                stage: "Transforming voice (local)...".to_string(),
                percent: 15.0,
            })
            .ok();

        let port = sidecar::ensure_running(&app).await?;
        if config.local_tts_mode == config::LocalTtsMode::Vc {
            log::info!("[pipeline] Using voice conversion (CosyVoice S2S)");
            local_tts::voice_convert(
                port,
                &config.local_voice_profile_id,
                &extracted_wav,
                &transformed_audio,
            ).await?;
        } else {
            log::info!("[pipeline] Using text-to-speech (Qwen TTS)");
            local_tts::speech_to_speech(
                port,
                &config.local_voice_profile_id,
                &extracted_wav,
                &transformed_audio,
                video_duration,
            ).await?;
        }
    } else {
        on_event
            .send(PipelineEvent::Progress {
                stage: "Transforming voice (ElevenLabs)...".to_string(),
                percent: 15.0,
            })
            .ok();

        elevenlabs::speech_to_speech(
            &config.elevenlabs_api_key,
            voice_id.as_deref().ok_or_else(|| "ElevenLabs voice ID is required but not configured".to_string())?,
            &extracted_wav,
            &transformed_audio,
        ).await?;
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
    crate::commands::recording::cleanup_stale_recordings(
        std::time::Duration::from_secs(3600),
    );

    Ok(final_path.to_string_lossy().to_string())
}

fn cleanup_temp(path: &Path) {
    std::fs::remove_file(path).ok();
}

fn chrono_timestamp() -> String {
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
    fn chrono_timestamp_returns_numeric_string() {
        let ts = chrono_timestamp();
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
}

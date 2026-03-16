use crate::config;
use crate::elevenlabs;
use crate::ffmpeg;
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
    on_event: Channel<PipelineEvent>,
) -> Result<String, String> {
    let recording = PathBuf::from(&recording_path);
    if !recording.exists() {
        return Err("Recording file not found".to_string());
    }

    log::info!("[pipeline] Starting: voice_replacement={}, input={}", voice_replacement, recording_path);

    let config = config::get_config(app.clone())?;
    let output_dir = PathBuf::from(&config.output_dir);
    std::fs::create_dir_all(&output_dir).map_err(|e| e.to_string())?;

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
    let api_key = &config.elevenlabs_api_key;
    if api_key.is_empty() {
        return Err("ElevenLabs API key not set — configure in Settings".to_string());
    }

    let default_voice = config
        .voices
        .iter()
        .find(|v| v.is_default)
        .or_else(|| config.voices.first());

    let voice_id = match default_voice {
        Some(v) => v.id.clone(),
        None => return Err("No voice configured — add one in Settings".to_string()),
    };

    let temp_dir = recording.parent().unwrap_or(std::path::Path::new("/tmp"));
    let extracted_wav = temp_dir.join(format!("extracted-{timestamp}.wav"));
    let transformed_mp3 = temp_dir.join(format!("transformed-{timestamp}.mp3"));

    // Stage 1: Extract audio (0-10%)
    on_event
        .send(PipelineEvent::Progress {
            stage: "Extracting audio".to_string(),
            percent: 5.0,
        })
        .ok();

    log::info!("[pipeline] Extracting audio to {:?}", extracted_wav);
    ffmpeg::extract_audio(&recording, &extracted_wav).await?;
    log::info!("[pipeline] Audio extracted");

    on_event
        .send(PipelineEvent::Progress {
            stage: "Extracting audio".to_string(),
            percent: 10.0,
        })
        .ok();

    // Stage 2: ElevenLabs S2S (10-85%)
    on_event
        .send(PipelineEvent::Progress {
            stage: "Transforming voice".to_string(),
            percent: 15.0,
        })
        .ok();

    elevenlabs::speech_to_speech(api_key, &voice_id, &extracted_wav, &transformed_mp3).await?;

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
    ffmpeg::replace_audio(&recording, &transformed_mp3, &final_path).await?;

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

    // Cleanup temp files
    cleanup_temp(&recording);
    cleanup_temp(&extracted_wav);
    cleanup_temp(&transformed_mp3);

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

//! Speech-to-speech voice conversion, one contract for every provider: source audio in,
//! the same speech in another voice out, at the source's length.

use crate::audio_split;
use crate::config::AppConfig;
use crate::elevenlabs;
use crate::ffmpeg;
use crate::local_tts;
use crate::sidecar;
use crate::tts_provider::Provider;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use tauri::Manager;

/// ElevenLabs refuses voice-changer input over 300s; pieces stay under it with room to spare.
const ELEVENLABS_MAX_PIECE_SECS: f64 = 290.0;
/// How far back from each piece limit to look for a pause to cut in.
const CUT_SEARCH_SECS: f64 = 20.0;

/// The voice a conversion should use: an ElevenLabs voice or a local voice profile.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VoiceChoice {
    pub provider: Provider,
    pub voice_id: String,
}

/// Pick the voice for a conversion: the explicit choice, else the Settings default for the active provider.
pub fn resolve_voice(
    config: &AppConfig,
    choice: Option<VoiceChoice>,
) -> Result<VoiceChoice, String> {
    if let Some(choice) = choice.filter(|c| !c.voice_id.is_empty()) {
        return Ok(choice);
    }
    let voice_id = match config.provider {
        Provider::ElevenLabs => config
            .voices
            .iter()
            .find(|v| v.is_default)
            .or_else(|| config.voices.first())
            .map(|v| v.id.clone())
            .ok_or("No ElevenLabs voice configured — add one in Settings")?,
        Provider::Local => {
            if config.local_voice_profile_id.is_empty() {
                return Err(
                    "No local voice profile configured — select one in Settings".to_string()
                );
            }
            config.local_voice_profile_id.clone()
        }
    };
    Ok(VoiceChoice {
        provider: config.provider.clone(),
        voice_id,
    })
}

/// Human-readable name of a voice, for the library's metadata.
pub async fn voice_name(
    app: &tauri::AppHandle,
    config: &AppConfig,
    choice: &VoiceChoice,
) -> Option<String> {
    match choice.provider {
        Provider::ElevenLabs => config
            .voices
            .iter()
            .find(|v| v.id == choice.voice_id)
            .map(|v| v.name.clone()),
        Provider::Local => match local_tts::list_local_voices(app.clone()).await {
            Ok(voices) => voices
                .into_iter()
                .find(|v| v.id == choice.voice_id)
                .map(|v| v.name),
            Err(e) => {
                log::warn!("[conversion] Could not resolve local voice name: {}", e);
                None
            }
        },
    }
}

/// Tracks the one conversion allowed to run; starting another or cancelling makes older runs stale.
#[derive(Default)]
pub struct ConversionRuns {
    current: AtomicU64,
}

impl ConversionRuns {
    /// Start a run, superseding any run already in progress, and return its token.
    pub fn begin(&self) -> u64 {
        self.current.fetch_add(1, Ordering::SeqCst) + 1
    }

    /// Cancel whatever run is in progress.
    pub fn cancel(&self) {
        self.current.fetch_add(1, Ordering::SeqCst);
    }

    /// True once `token`'s run has been cancelled or superseded.
    pub fn is_stale(&self, token: u64) -> bool {
        self.current.load(Ordering::SeqCst) != token
    }
}

/// Cancel the conversion in progress, if any.
#[tauri::command]
pub fn cancel_conversion(app: tauri::AppHandle) {
    app.state::<ConversionRuns>().cancel();
    log::info!("[conversion] Cancel requested");
}

/// Convert `source_wav` (16kHz mono PCM) into `choice`'s voice, writing files under `work_dir`.
///
/// Returns the converted audio's path. `on_progress` receives 0.0..=1.0; the run stops when `is_cancelled` turns true.
#[allow(clippy::too_many_arguments)]
pub async fn convert(
    app: &tauri::AppHandle,
    config: &AppConfig,
    choice: &VoiceChoice,
    source_wav: &Path,
    work_dir: &Path,
    stamp: &str,
    duration: Option<f64>,
    on_progress: &(dyn Fn(f32) + Send + Sync),
    is_cancelled: &(dyn Fn() -> bool + Send + Sync),
) -> Result<PathBuf, String> {
    match choice.provider {
        Provider::Local => {
            let output = work_dir.join(format!("transformed-{stamp}.wav"));
            let port = sidecar::ensure_running(app).await?;
            let http = app.state::<local_tts::HttpClient>();
            local_tts::voice_convert(
                &http.client,
                port,
                &choice.voice_id,
                source_wav,
                &output,
                duration,
                &|p| on_progress(p.done as f32 / p.total.max(1) as f32),
                is_cancelled,
            )
            .await?;
            Ok(output)
        }
        Provider::ElevenLabs => {
            if config.elevenlabs_api_key.is_empty() {
                return Err("ElevenLabs API key not set — configure in Settings".to_string());
            }
            convert_elevenlabs(
                app,
                &config.elevenlabs_api_key,
                &choice.voice_id,
                source_wav,
                work_dir,
                stamp,
                on_progress,
                is_cancelled,
            )
            .await
        }
    }
}

/// Run ElevenLabs speech-to-speech, splitting at pauses when the source is over its per-request limit.
#[allow(clippy::too_many_arguments)]
async fn convert_elevenlabs(
    app: &tauri::AppHandle,
    api_key: &str,
    voice_id: &str,
    source_wav: &Path,
    work_dir: &Path,
    stamp: &str,
    on_progress: &(dyn Fn(f32) + Send + Sync),
    is_cancelled: &(dyn Fn() -> bool + Send + Sync),
) -> Result<PathBuf, String> {
    let audio = audio_split::read_pcm16_mono(source_wav)?;
    let cuts = audio_split::quiet_cut_points(&audio, ELEVENLABS_MAX_PIECE_SECS, CUT_SEARCH_SECS);
    if cuts.is_empty() {
        let output = work_dir.join(format!("transformed-{stamp}.mp3"));
        elevenlabs::speech_to_speech(app, api_key, voice_id, source_wav, &output).await?;
        on_progress(1.0);
        return Ok(output);
    }

    let mut bounds = vec![0];
    bounds.extend(&cuts);
    bounds.push(audio.samples.len());
    log::info!(
        "[conversion] ElevenLabs: {:.1}s source split into {} pieces at pauses",
        audio.duration_secs(),
        bounds.len() - 1,
    );

    let mut converted = Vec::new();
    let mut temp_files = Vec::new();
    let result: Result<PathBuf, String> = async {
        for (i, pair) in bounds.windows(2).enumerate() {
            if is_cancelled() {
                return Err(local_tts::CANCELLED.to_string());
            }
            let piece_wav = work_dir.join(format!("piece-{stamp}-{i}.wav"));
            let piece_mp3 = work_dir.join(format!("piece-{stamp}-{i}.mp3"));
            temp_files.push(piece_wav.clone());
            temp_files.push(piece_mp3.clone());
            audio_split::write_pcm16_mono(
                &piece_wav,
                &audio.samples[pair[0]..pair[1]],
                audio.sample_rate,
            )?;
            elevenlabs::speech_to_speech(app, api_key, voice_id, &piece_wav, &piece_mp3).await?;
            converted.push((
                piece_mp3,
                (pair[1] - pair[0]) as f64 / audio.sample_rate as f64,
            ));
            on_progress((i + 1) as f32 / (bounds.len() - 1) as f32);
        }
        let output = work_dir.join(format!("transformed-{stamp}.wav"));
        ffmpeg::concat_exact(&converted, &output).await?;
        Ok(output)
    }
    .await;
    for f in temp_files {
        std::fs::remove_file(f).ok();
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::Voice;

    fn config_with(provider: Provider) -> AppConfig {
        AppConfig {
            provider,
            voices: vec![
                Voice {
                    id: "el-1".into(),
                    name: "First".into(),
                    description: String::new(),
                    is_default: false,
                },
                Voice {
                    id: "el-2".into(),
                    name: "Default".into(),
                    description: String::new(),
                    is_default: true,
                },
            ],
            local_voice_profile_id: "local-9".into(),
            ..AppConfig::default()
        }
    }

    #[test]
    fn explicit_choice_wins_over_settings() {
        let choice = VoiceChoice {
            provider: Provider::Local,
            voice_id: "other".into(),
        };
        let resolved =
            resolve_voice(&config_with(Provider::ElevenLabs), Some(choice.clone())).unwrap();
        assert_eq!(resolved, choice);
    }

    #[test]
    fn falls_back_to_default_elevenlabs_voice() {
        let resolved = resolve_voice(&config_with(Provider::ElevenLabs), None).unwrap();
        assert_eq!(
            resolved,
            VoiceChoice {
                provider: Provider::ElevenLabs,
                voice_id: "el-2".into()
            }
        );
    }

    #[test]
    fn falls_back_to_local_profile() {
        let resolved = resolve_voice(&config_with(Provider::Local), None).unwrap();
        assert_eq!(
            resolved,
            VoiceChoice {
                provider: Provider::Local,
                voice_id: "local-9".into()
            }
        );
    }

    #[test]
    fn empty_choice_is_treated_as_no_choice() {
        let empty = VoiceChoice {
            provider: Provider::Local,
            voice_id: String::new(),
        };
        let resolved = resolve_voice(&config_with(Provider::ElevenLabs), Some(empty)).unwrap();
        assert_eq!(resolved.voice_id, "el-2");
    }

    #[test]
    fn missing_local_profile_is_an_error() {
        let mut config = config_with(Provider::Local);
        config.local_voice_profile_id.clear();
        assert!(resolve_voice(&config, None).is_err());
    }

    #[test]
    fn voice_choice_uses_camel_case_json() {
        let choice: VoiceChoice =
            serde_json::from_str(r#"{"provider":"local","voiceId":"p1"}"#).unwrap();
        assert_eq!(
            choice,
            VoiceChoice {
                provider: Provider::Local,
                voice_id: "p1".into()
            }
        );
    }

    #[test]
    fn starting_a_run_makes_the_previous_one_stale() {
        let runs = ConversionRuns::default();
        let first = runs.begin();
        assert!(!runs.is_stale(first));
        let second = runs.begin();
        assert!(runs.is_stale(first));
        assert!(!runs.is_stale(second));
        runs.cancel();
        assert!(runs.is_stale(second));
    }
}

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::Manager;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Voice {
    pub id: String,
    pub name: String,
    pub description: String,
    pub is_default: bool,
}

/// Position of the webcam bubble overlay in the recording.
/// Valid positions: bottom-left, bottom-right.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
pub enum WebcamPosition {
    #[serde(rename = "bottom-left")]
    BottomLeft,
    #[default]
    #[serde(rename = "bottom-right")]
    BottomRight,
}

/// Custom deserializer that falls back to the default position for unknown values.
fn deserialize_webcam_position<'de, D>(deserializer: D) -> Result<WebcamPosition, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    match s.as_str() {
        "bottom-left" => Ok(WebcamPosition::BottomLeft),
        "bottom-right" => Ok(WebcamPosition::BottomRight),
        _ => Ok(WebcamPosition::default()),
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preferences {
    pub default_capture_mode: String,
    /// Whether the webcam overlay is enabled during recording
    pub webcam_enabled: bool,
    pub voice_replacement_enabled: bool,
    /// Position of the webcam overlay bubble
    #[serde(default, deserialize_with = "deserialize_webcam_position")]
    pub webcam_position: WebcamPosition,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            default_capture_mode: "fullscreen".to_string(),
            webcam_enabled: false,
            voice_replacement_enabled: true,
            webcam_position: WebcamPosition::default(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GoogleDrive {
    #[serde(default)]
    pub client_id: String,
    #[serde(default)]
    pub client_secret: String,
    #[serde(default)]
    pub access_token: String,
    #[serde(default)]
    pub refresh_token: String,
    #[serde(default)]
    pub email: String,
    #[serde(default)]
    pub connected: bool,
    /// Unix timestamp (seconds) when the access token expires
    #[serde(default)]
    pub expires_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(default)]
    pub elevenlabs_api_key: String,
    #[serde(default)]
    pub voices: Vec<Voice>,
    #[serde(default = "default_output_dir")]
    pub output_dir: String,
    #[serde(default)]
    pub preferences: Preferences,
    #[serde(default)]
    pub google_drive: GoogleDrive,
    #[serde(default)]
    pub secrets_migrated: bool,
    /// TTS provider: "elevenlabs" or "local"
    #[serde(default = "default_provider")]
    pub provider: String,
    /// Endpoint for the local Voicebox server
    #[serde(default = "default_local_endpoint")]
    pub local_endpoint: String,
    /// Voice profile ID to use with the local Voicebox server
    #[serde(default)]
    pub local_voice_profile_id: String,
    /// Local TTS mode: "tts" (text-to-speech via Qwen) or "vc" (voice conversion via CosyVoice)
    #[serde(default = "default_local_tts_mode")]
    pub local_tts_mode: String,
}

fn default_local_tts_mode() -> String {
    "tts".to_string()
}

fn default_output_dir() -> String {
    dirs::video_dir()
        .or_else(dirs::home_dir)
        .map(|p| p.join("VoiceOver").to_string_lossy().to_string())
        .unwrap_or_else(|| "~/VoiceOver".to_string())
}

fn default_provider() -> String {
    "elevenlabs".to_string()
}

fn default_local_endpoint() -> String {
    "http://localhost:17493".to_string()
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            elevenlabs_api_key: String::new(),
            voices: Vec::new(),
            output_dir: default_output_dir(),
            preferences: Preferences::default(),
            google_drive: GoogleDrive::default(),
            secrets_migrated: false,
            provider: default_provider(),
            local_endpoint: default_local_endpoint(),
            local_voice_profile_id: String::new(),
            local_tts_mode: default_local_tts_mode(),
        }
    }
}

fn config_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&data_dir).map_err(|e| format!("Failed to create app data dir: {e}"))?;
    Ok(data_dir.join("config.json"))
}

#[tauri::command]
pub async fn get_config(app: tauri::AppHandle) -> Result<AppConfig, String> {
    let path = config_path(&app)?;
    tokio::task::spawn_blocking(move || {
        let mut config = if path.exists() {
            let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
            serde_json::from_str(&content).map_err(|e| e.to_string())?
        } else {
            // Seed from static/_config.json if it exists (user may have placed config there)
            let config = read_static_config().unwrap_or_default();
            let json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
            fs::write(&path, json).map_err(|e| e.to_string())?;
            config
        };

        // Migrate: if config.json still has secrets (pre-keychain), move them to keychain
        if !config.secrets_migrated
            && (!config.elevenlabs_api_key.is_empty()
                || !config.google_drive.client_secret.is_empty()
                || !config.google_drive.access_token.is_empty()
                || !config.google_drive.refresh_token.is_empty())
        {
            log::info!("[config] Migrating secrets from config.json to keychain");
            crate::secrets::save_secrets(&config);
            // Strip secrets from file, set sentinel, and rewrite
            let mut sanitized = config.clone();
            crate::secrets::sanitize_config(&mut sanitized);
            sanitized.secrets_migrated = true;
            let json = serde_json::to_string_pretty(&sanitized).map_err(|e| e.to_string())?;
            fs::write(&path, json).map_err(|e| format!("Failed to write migrated config: {e}"))?;
        }

        // Always overlay secrets from keychain (authoritative source)
        crate::secrets::load_secrets(&mut config);

        Ok(config)
    }).await.map_err(|e| format!("Config task failed: {e}"))?
}

/// Try reading config from static/_config.json (project root).
#[cfg(debug_assertions)]
fn read_static_config() -> Option<AppConfig> {
    let candidates = [
        std::env::current_exe()
            .ok()
            .and_then(|exe| exe.ancestors().find_map(|a| {
                let p = a.join("static/_config.json");
                p.exists().then_some(p)
            })),
        {
            let p = PathBuf::from("static/_config.json");
            p.exists().then_some(p)
        },
    ];
    for candidate in candidates.into_iter().flatten() {
        if let Ok(content) = fs::read_to_string(&candidate) {
            if let Ok(config) = serde_json::from_str::<AppConfig>(&content) {
                return Some(config);
            }
        }
    }
    None
}

#[cfg(not(debug_assertions))]
fn read_static_config() -> Option<AppConfig> {
    None
}

#[tauri::command]
pub async fn save_config(app: tauri::AppHandle, config: AppConfig) -> Result<(), String> {
    let path = config_path(&app)?;
    tokio::task::spawn_blocking(move || {
        // Store secrets in OS keychain
        crate::secrets::save_secrets(&config);

        // Strip secrets before writing to file
        let mut file_config = config.clone();
        crate::secrets::sanitize_config(&mut file_config);

        let json = serde_json::to_string_pretty(&file_config).map_err(|e| e.to_string())?;
        fs::write(&path, &json).map_err(|e| e.to_string())?;

        // Sync non-secret config to static dir in dev mode
        sync_to_static(&file_config);

        Ok(())
    }).await.map_err(|e| format!("Config save task failed: {e}"))?
}

/// Write config to the project's static dir so the Vite dev server can serve it.
/// This bridges the gap between Tauri's app data and the browser at localhost.
/// The file is gitignored so credentials are safe from accidental commits.
#[cfg(debug_assertions)]
fn sync_to_static(config: &AppConfig) {
    let json = serde_json::to_string_pretty(config).unwrap_or_default();

    // Walk up from the binary to find the project root (src-tauri/../static)
    if let Ok(exe) = std::env::current_exe() {
        // In dev: target/debug/voiceover -> src-tauri -> voiceover -> static
        for ancestor in exe.ancestors() {
            let static_dir = ancestor.join("static");
            if static_dir.is_dir() {
                fs::write(static_dir.join("_config.json"), &json).ok();
                return;
            }
        }
    }
    // Fallback: try CWD
    let static_dir = PathBuf::from("static");
    if static_dir.is_dir() {
        fs::write(static_dir.join("_config.json"), &json).ok();
    }
}

#[cfg(not(debug_assertions))]
fn sync_to_static(_config: &AppConfig) {
    // no-op in production
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_has_empty_api_key() {
        let config = AppConfig::default();
        assert!(config.elevenlabs_api_key.is_empty());
    }

    #[test]
    fn default_config_has_no_voices() {
        let config = AppConfig::default();
        assert!(config.voices.is_empty());
    }

    #[test]
    fn default_preferences_enable_voice_replacement() {
        let prefs = Preferences::default();
        assert!(prefs.voice_replacement_enabled);
    }

    #[test]
    fn default_preferences_disable_webcam() {
        let prefs = Preferences::default();
        assert!(!prefs.webcam_enabled);
    }

    #[test]
    fn default_preferences_use_fullscreen_capture() {
        let prefs = Preferences::default();
        assert_eq!(prefs.default_capture_mode, "fullscreen");
    }

    #[test]
    fn default_output_dir_contains_voiceover() {
        let dir = default_output_dir();
        assert!(dir.contains("VoiceOver"), "expected 'VoiceOver' in output dir, got: {dir}");
    }

    #[test]
    fn default_google_drive_is_disconnected() {
        let gd = GoogleDrive::default();
        assert!(!gd.connected);
        assert!(gd.access_token.is_empty());
        assert!(gd.refresh_token.is_empty());
        assert_eq!(gd.expires_at, 0);
    }

    #[test]
    fn config_serialization_roundtrip_is_lossless() {
        let config = AppConfig {
            elevenlabs_api_key: "test-not-a-real-key".to_string(),
            voices: vec![Voice {
                id: "voice1".to_string(),
                name: "Test Voice".to_string(),
                description: "A test voice".to_string(),
                is_default: true,
            }],
            output_dir: "/tmp/test-output".to_string(),
            preferences: Preferences {
                default_capture_mode: "window".to_string(),
                webcam_enabled: true,
                voice_replacement_enabled: false,
                webcam_position: WebcamPosition::BottomLeft,
            },
            google_drive: GoogleDrive {
                client_id: "cid".to_string(),
                client_secret: "csec".to_string(),
                access_token: "at".to_string(),
                refresh_token: "rt".to_string(),
                email: "test@example.com".to_string(),
                connected: true,
                expires_at: 1700000000,
            },
            secrets_migrated: false,
            provider: "elevenlabs".to_string(),
            local_endpoint: "http://localhost:17493".to_string(),
            local_voice_profile_id: String::new(),
            local_tts_mode: "tts".to_string(),
        };

        let json = serde_json::to_string(&config).unwrap();
        let deserialized: AppConfig = serde_json::from_str(&json).unwrap();

        assert_eq!(deserialized.elevenlabs_api_key, "test-not-a-real-key");
        assert_eq!(deserialized.voices.len(), 1);
        assert_eq!(deserialized.voices[0].id, "voice1");
        assert_eq!(deserialized.voices[0].is_default, true);
        assert_eq!(deserialized.output_dir, "/tmp/test-output");
        assert_eq!(deserialized.preferences.default_capture_mode, "window");
        assert_eq!(deserialized.preferences.webcam_enabled, true);
        assert_eq!(deserialized.preferences.voice_replacement_enabled, false);
        assert_eq!(deserialized.preferences.webcam_position, WebcamPosition::BottomLeft);
        assert_eq!(deserialized.google_drive.connected, true);
        assert_eq!(deserialized.google_drive.expires_at, 1700000000);
    }

    #[test]
    fn config_deserialization_with_missing_fields_uses_defaults() {
        let json = r#"{"elevenlabs_api_key": "sk-old"}"#;
        let config: AppConfig = serde_json::from_str(json).unwrap();

        assert_eq!(config.elevenlabs_api_key, "sk-old");
        assert!(config.voices.is_empty());
        assert!(config.output_dir.contains("VoiceOver"));
        assert_eq!(config.preferences.default_capture_mode, "fullscreen");
        assert!(config.preferences.voice_replacement_enabled);
        assert!(!config.preferences.webcam_enabled);
        assert_eq!(config.preferences.webcam_position, WebcamPosition::BottomRight);
        assert!(!config.google_drive.connected);
    }

    #[test]
    fn invalid_webcam_position_falls_back_to_default() {
        let json = r#"{
            "preferences": {
                "default_capture_mode": "fullscreen",
                "webcam_enabled": false,
                "voice_replacement_enabled": true,
                "webcam_position": "top-center"
            }
        }"#;
        let config: AppConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.preferences.webcam_position, WebcamPosition::BottomRight);
    }
}

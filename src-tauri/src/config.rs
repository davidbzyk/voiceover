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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preferences {
    pub default_capture_mode: String,
    pub webcam_enabled: bool,
    pub voice_replacement_enabled: bool,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            default_capture_mode: "fullscreen".to_string(),
            webcam_enabled: false,
            voice_replacement_enabled: true,
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
}

fn default_output_dir() -> String {
    dirs::video_dir()
        .or_else(dirs::home_dir)
        .map(|p| p.join("VoiceOver").to_string_lossy().to_string())
        .unwrap_or_else(|| "~/VoiceOver".to_string())
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            elevenlabs_api_key: String::new(),
            voices: Vec::new(),
            output_dir: default_output_dir(),
            preferences: Preferences::default(),
            google_drive: GoogleDrive::default(),
        }
    }
}

fn config_path(app: &tauri::AppHandle) -> PathBuf {
    let data_dir = app.path().app_data_dir().expect("failed to get app data dir");
    fs::create_dir_all(&data_dir).ok();
    data_dir.join("config.json")
}

#[tauri::command]
pub fn get_config(app: tauri::AppHandle) -> Result<AppConfig, String> {
    let path = config_path(&app);
    if path.exists() {
        let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())
    } else {
        let config = AppConfig::default();
        let json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
        fs::write(&path, json).map_err(|e| e.to_string())?;
        Ok(config)
    }
}

#[tauri::command]
pub fn save_config(app: tauri::AppHandle, config: AppConfig) -> Result<(), String> {
    let path = config_path(&app);
    let json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(&path, &json).map_err(|e| e.to_string())?;

    // Also write to static/ so the browser dev server can serve it
    sync_to_static(&json);

    Ok(())
}

/// Write config to the project's static dir so the Vite dev server can serve it.
/// This bridges the gap between Tauri's app data and the browser at localhost.
fn sync_to_static(json: &str) {
    // Walk up from the binary to find the project root (src-tauri/../static)
    if let Ok(exe) = std::env::current_exe() {
        // In dev: target/debug/voiceover -> src-tauri -> voiceover -> static
        for ancestor in exe.ancestors() {
            let static_dir = ancestor.join("static");
            if static_dir.is_dir() {
                fs::write(static_dir.join("_config.json"), json).ok();
                return;
            }
        }
    }
    // Fallback: try CWD
    let static_dir = PathBuf::from("static");
    if static_dir.is_dir() {
        fs::write(static_dir.join("_config.json"), json).ok();
    }
}

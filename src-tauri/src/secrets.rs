use keyring::Entry;
use serde::{Deserialize, Serialize};

const SERVICE: &str = "com.voiceover.app";
const ACCOUNT: &str = "credentials";

/// All secrets stored as a single JSON blob in one keychain entry
#[derive(Debug, Default, Serialize, Deserialize)]
struct Vault {
    #[serde(default)]
    elevenlabs_api_key: String,
    #[serde(default)]
    google_drive_client_secret: String,
    #[serde(default)]
    google_drive_access_token: String,
    #[serde(default)]
    google_drive_refresh_token: String,
}

fn entry() -> Result<Entry, String> {
    Entry::new(SERVICE, ACCOUNT).map_err(|e| format!("Keychain entry error: {e}"))
}

fn read_vault() -> Vault {
    let Ok(e) = entry() else { return Vault::default() };
    match e.get_password() {
        Ok(json) => serde_json::from_str(&json).unwrap_or_default(),
        Err(keyring::Error::NoEntry) => Vault::default(),
        Err(err) => {
            log::warn!("[secrets] Failed to read keychain: {err}");
            Vault::default()
        }
    }
}

fn write_vault(vault: &Vault) {
    let Ok(e) = entry() else { return };
    let Ok(json) = serde_json::to_string(vault) else {
        log::error!("[secrets] Failed to serialize vault — aborting write to prevent data loss");
        return;
    };
    if let Err(err) = e.set_password(&json) {
        log::error!("[secrets] Failed to write keychain: {err}");
    }
}

/// Load secrets from keychain and merge into an AppConfig
pub fn load_secrets(config: &mut super::config::AppConfig) {
    let vault = read_vault();
    if !vault.elevenlabs_api_key.is_empty() {
        config.elevenlabs_api_key = vault.elevenlabs_api_key;
    }
    if !vault.google_drive_client_secret.is_empty() {
        config.google_drive.client_secret = vault.google_drive_client_secret;
    }
    if !vault.google_drive_access_token.is_empty() {
        config.google_drive.access_token = vault.google_drive_access_token;
    }
    if !vault.google_drive_refresh_token.is_empty() {
        config.google_drive.refresh_token = vault.google_drive_refresh_token;
    }
}

/// Store secrets from AppConfig into keychain
pub fn save_secrets(config: &super::config::AppConfig) {
    let vault = Vault {
        elevenlabs_api_key: config.elevenlabs_api_key.clone(),
        google_drive_client_secret: config.google_drive.client_secret.clone(),
        google_drive_access_token: config.google_drive.access_token.clone(),
        google_drive_refresh_token: config.google_drive.refresh_token.clone(),
    };
    write_vault(&vault);
}

/// Remove all secrets from keychain
#[allow(dead_code)]
pub fn clear_secrets() {
    if let Ok(e) = entry() {
        let _ = e.delete_credential();
    }
}

/// Strip secrets from an AppConfig (for safe file storage)
pub fn sanitize_config(config: &mut super::config::AppConfig) {
    config.elevenlabs_api_key = String::new();
    config.google_drive.client_secret = String::new();
    config.google_drive.access_token = String::new();
    config.google_drive.refresh_token = String::new();
}

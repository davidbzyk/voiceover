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

fn read_vault() -> Option<Vault> {
    let Ok(e) = entry() else { return None };
    match e.get_password() {
        Ok(json) => Some(serde_json::from_str(&json).unwrap_or_default()),
        Err(keyring::Error::NoEntry) => Some(Vault::default()),
        Err(err) => {
            log::warn!("[secrets] Failed to read keychain: {err}");
            None // Hard failure — don't return empty vault
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
    let Some(vault) = read_vault() else {
        log::warn!("[secrets] Keychain unavailable — keeping config as-is");
        return;
    };
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

/// Remove all secrets from keychain.
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::AppConfig;

    #[test]
    fn sanitize_config_clears_all_secret_fields() {
        let mut config = AppConfig::default();
        config.elevenlabs_api_key = "sk-test".to_string();
        config.google_drive.client_secret = "secret".to_string();
        config.google_drive.access_token = "at-123".to_string();
        config.google_drive.refresh_token = "rt-456".to_string();
        // Non-secret fields
        config.google_drive.client_id = "cid".to_string();
        config.google_drive.email = "test@test.com".to_string();

        sanitize_config(&mut config);

        assert!(config.elevenlabs_api_key.is_empty());
        assert!(config.google_drive.client_secret.is_empty());
        assert!(config.google_drive.access_token.is_empty());
        assert!(config.google_drive.refresh_token.is_empty());
        // Non-secret fields preserved
        assert_eq!(config.google_drive.client_id, "cid");
        assert_eq!(config.google_drive.email, "test@test.com");
    }

    #[test]
    fn sanitize_config_preserves_non_secret_preferences() {
        let mut config = AppConfig::default();
        config.output_dir = "/custom/path".to_string();
        config.preferences.webcam_enabled = true;
        config.voices = vec![crate::config::Voice {
            id: "v1".to_string(),
            name: "Test".to_string(),
            description: "".to_string(),
            is_default: true,
        }];

        sanitize_config(&mut config);

        assert_eq!(config.output_dir, "/custom/path");
        assert!(config.preferences.webcam_enabled);
        assert_eq!(config.voices.len(), 1);
    }

    #[test]
    fn vault_serialization_roundtrip() {
        let vault = Vault {
            elevenlabs_api_key: "key123".to_string(),
            google_drive_client_secret: "sec".to_string(),
            google_drive_access_token: "at".to_string(),
            google_drive_refresh_token: "rt".to_string(),
        };
        let json = serde_json::to_string(&vault).unwrap();
        let parsed: Vault = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.elevenlabs_api_key, "key123");
        assert_eq!(parsed.google_drive_client_secret, "sec");
        assert_eq!(parsed.google_drive_access_token, "at");
        assert_eq!(parsed.google_drive_refresh_token, "rt");
    }

    #[test]
    fn vault_deserialization_with_missing_fields_uses_defaults() {
        let json = r#"{"elevenlabs_api_key": "key"}"#;
        let vault: Vault = serde_json::from_str(json).unwrap();
        assert_eq!(vault.elevenlabs_api_key, "key");
        assert!(vault.google_drive_client_secret.is_empty());
        assert!(vault.google_drive_access_token.is_empty());
        assert!(vault.google_drive_refresh_token.is_empty());
    }

    #[test]
    fn load_secrets_only_overwrites_non_empty_vault_fields() {
        // This tests the logic without hitting the keychain.
        // We test the overlay behavior by simulating what load_secrets does.
        let vault = Vault {
            elevenlabs_api_key: "new-key".to_string(),
            google_drive_client_secret: String::new(), // empty = don't overwrite
            google_drive_access_token: "new-token".to_string(),
            google_drive_refresh_token: String::new(),
        };

        let mut config = AppConfig::default();
        config.elevenlabs_api_key = "old-key".to_string();
        config.google_drive.client_secret = "old-secret".to_string();

        // Simulate load_secrets overlay logic
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

        assert_eq!(config.elevenlabs_api_key, "new-key");
        assert_eq!(config.google_drive.client_secret, "old-secret"); // preserved
        assert_eq!(config.google_drive.access_token, "new-token");
        assert!(config.google_drive.refresh_token.is_empty());
    }
}

use crate::ffmpeg::resolve_ffmpeg_path;
use std::process::Command;

/// Check if ffmpeg is available (bundled sidecar or system PATH).
pub fn check_ffmpeg() -> bool {
    Command::new(resolve_ffmpeg_path())
        .arg("-version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

#[tauri::command]
pub fn check_prerequisites() -> Result<PrerequisiteStatus, String> {
    let ffmpeg_available = check_ffmpeg();
    let ffmpeg_version = if ffmpeg_available {
        Command::new(resolve_ffmpeg_path())
            .arg("-version")
            .output()
            .ok()
            .and_then(|o| String::from_utf8(o.stdout).ok())
            .and_then(|s| s.lines().next().map(|l| l.to_string()))
    } else {
        None
    };

    Ok(PrerequisiteStatus {
        ffmpeg_available,
        ffmpeg_version,
    })
}

#[derive(serde::Serialize)]
pub struct PrerequisiteStatus {
    pub ffmpeg_available: bool,
    pub ffmpeg_version: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json;

    #[test]
    fn check_ffmpeg_returns_bool_without_panic() {
        let result = check_ffmpeg();
        // Just verify it returns a bool without panicking
        assert!(result == true || result == false);
    }

    #[test]
    fn prerequisite_status_serializes_correctly() {
        let status = PrerequisiteStatus {
            ffmpeg_available: true,
            ffmpeg_version: Some("ffmpeg version 6.1".to_string()),
        };
        let json: serde_json::Value = serde_json::to_value(&status).unwrap();
        assert_eq!(json["ffmpeg_available"], true);
        assert_eq!(json["ffmpeg_version"], "ffmpeg version 6.1");
    }

    #[test]
    fn prerequisite_status_serializes_with_null_version() {
        let status = PrerequisiteStatus {
            ffmpeg_available: false,
            ffmpeg_version: None,
        };
        let json: serde_json::Value = serde_json::to_value(&status).unwrap();
        assert_eq!(json["ffmpeg_available"], false);
        assert!(json["ffmpeg_version"].is_null());
    }
}

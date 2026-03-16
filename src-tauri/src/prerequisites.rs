use std::process::Command;

/// Check if ffmpeg is available on the system PATH.
pub fn check_ffmpeg() -> bool {
    Command::new("ffmpeg")
        .arg("-version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

#[tauri::command]
pub fn check_prerequisites() -> Result<PrerequisiteStatus, String> {
    let ffmpeg_available = check_ffmpeg();
    let ffmpeg_version = if ffmpeg_available {
        Command::new("ffmpeg")
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

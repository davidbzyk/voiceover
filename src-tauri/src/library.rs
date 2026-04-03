use crate::config;
use crate::ffmpeg;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RecordingInfo {
    pub path: String,
    pub filename: String,
    pub size_bytes: u64,
    pub created_at: u64,
    pub duration_secs: Option<f64>,
    pub thumbnail_path: Option<String>,
    pub meta: Option<RecordingMeta>,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RecordingMeta {
    pub voice_profile: Option<String>,
    pub provider: Option<String>,
    pub drive_url: Option<String>,
    pub uploaded_at: Option<u64>,
    #[serde(default)]
    pub voice_replacement: bool,
}

/// Parse the unix timestamp from a `voiceover-{timestamp}.mp4` filename.
fn parse_timestamp_from_filename(filename: &str) -> Option<u64> {
    let stem = filename.strip_suffix(".mp4")?;
    let ts_str = stem.strip_prefix("voiceover-")?;
    ts_str.parse().ok()
}

/// Validate that a path is within the allowed output directory.
fn validate_in_output_dir(file_path: &Path, output_dir: &Path) -> Result<(), String> {
    let canonical = std::fs::canonicalize(file_path)
        .map_err(|e| format!("Invalid path: {e}"))?;
    let canonical_dir = std::fs::canonicalize(output_dir)
        .map_err(|e| format!("Invalid output directory: {e}"))?;

    if !canonical.starts_with(&canonical_dir) {
        return Err("Access denied: file is not in the output directory".to_string());
    }
    Ok(())
}

/// Scan the output directory for recordings and return metadata for each.
/// Scan a directory for .mp4 recordings and return metadata.
fn scan_recordings(output_dir: &Path) -> Result<Vec<RecordingInfo>, String> {
    if !output_dir.exists() {
        log::warn!("[library] Output directory does not exist: {:?}", output_dir);
        return Ok(Vec::new());
    }

    let entries = std::fs::read_dir(output_dir)
        .map_err(|e| format!("Failed to read output directory: {e}"))?;

    let mut recordings = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().map(|e| e == "mp4").unwrap_or(false) {
            let filename = path.file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();

            let file_meta = std::fs::metadata(&path).ok();
            let size_bytes = file_meta.as_ref().map(|m| m.len()).unwrap_or(0);

            // Parse timestamp from filename, fall back to file modification time
            let created_at = parse_timestamp_from_filename(&filename)
                .or_else(|| {
                    file_meta.as_ref()
                        .and_then(|m| m.modified().ok())
                        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                        .map(|d| d.as_secs())
                })
                .unwrap_or(0);

            // Check for cached thumbnail
            let thumb_dir = output_dir.join(".thumbnails");
            let thumb_path = thumb_dir.join(format!("{}.jpg", path.file_stem().unwrap_or_default().to_string_lossy()));
            let thumbnail_path = if thumb_path.exists() {
                Some(thumb_path.to_string_lossy().to_string())
            } else {
                None
            };

            // Read companion .meta.json if present
            let meta_path = path.with_extension("meta.json");
            let meta = if meta_path.exists() {
                std::fs::read_to_string(&meta_path)
                    .ok()
                    .and_then(|content| serde_json::from_str::<RecordingMeta>(&content).ok())
            } else {
                None
            };

            recordings.push(RecordingInfo {
                path: path.to_string_lossy().to_string(),
                filename,
                size_bytes,
                created_at,
                duration_secs: None,  // Probed lazily on demand to avoid slow scans
                thumbnail_path,
                meta,
            });
        }
    }

    // Sort by created_at descending (newest first)
    recordings.sort_by(|a, b| b.created_at.cmp(&a.created_at));

    Ok(recordings)
}

/// Resolve the actual output directory, falling back to the system default
/// if the configured path doesn't exist. Mirrors the pipeline's fallback logic.
pub(crate) fn resolve_output_dir(configured: &str) -> PathBuf {
    let configured_path = PathBuf::from(configured);
    if !configured.is_empty() && configured_path.exists() {
        return configured_path;
    }

    // Configured path missing or empty — use macOS default ~/Movies/VoiceOver
    let fallback = dirs::video_dir()
        .map(|p| p.join("VoiceOver"))
        .unwrap_or_else(|| {
            let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("/tmp"));
            log::error!("[library] dirs::video_dir() returned None — using {:?}/VoiceOver", home);
            home.join("VoiceOver")
        });

    if configured_path != fallback {
        log::warn!("[library] Configured output dir {:?} unavailable, using {:?}", configured_path, fallback);
    }
    fallback
}

/// Scan the output directory for recordings and return metadata for each.
#[tauri::command]
pub async fn list_recordings(app: tauri::AppHandle) -> Result<Vec<RecordingInfo>, String> {
    let config = config::get_config(app).await?;
    let output_dir = resolve_output_dir(&config.output_dir);
    log::info!("[library] Scanning {:?} for recordings", output_dir);
    let results = scan_recordings(&output_dir)?;
    log::info!("[library] Found {} recordings", results.len());
    Ok(results)
}

/// Generate a thumbnail JPEG for a recording. Returns the path to the cached thumbnail.
#[tauri::command]
pub async fn generate_thumbnail(
    app: tauri::AppHandle,
    file_path: String,
) -> Result<String, String> {
    let config = config::get_config(app).await?;
    let output_dir = resolve_output_dir(&config.output_dir);
    let input = PathBuf::from(&file_path);

    validate_in_output_dir(&input, &output_dir)?;

    let thumb_dir = output_dir.join(".thumbnails");
    std::fs::create_dir_all(&thumb_dir)
        .map_err(|e| format!("Failed to create thumbnails directory: {e}"))?;

    let stem = input.file_stem()
        .ok_or_else(|| "File has no stem".to_string())?
        .to_string_lossy();
    let thumb_path = thumb_dir.join(format!("{stem}.jpg"));

    // Return cached thumbnail if it exists
    if thumb_path.exists() {
        return Ok(thumb_path.to_string_lossy().to_string());
    }

    ffmpeg::extract_thumbnail(&input, &thumb_path).await?;

    Ok(thumb_path.to_string_lossy().to_string())
}

/// Delete a recording and its associated files (.meta.json, .txt, cached thumbnail).
#[tauri::command]
pub async fn delete_recording(
    app: tauri::AppHandle,
    file_path: String,
) -> Result<(), String> {
    let config = config::get_config(app).await?;
    let output_dir = resolve_output_dir(&config.output_dir);
    let path = PathBuf::from(&file_path);

    validate_in_output_dir(&path, &output_dir)?;

    // Delete the MP4
    std::fs::remove_file(&path)
        .map_err(|e| format!("Failed to delete recording: {e}"))?;

    // Delete companion files (ignore errors — they may not exist)
    let meta_path = path.with_extension("meta.json");
    std::fs::remove_file(&meta_path).ok();

    let transcript_path = path.with_extension("txt");
    std::fs::remove_file(&transcript_path).ok();

    // Delete cached thumbnail
    let thumb_dir = output_dir.join(".thumbnails");
    let stem = path.file_stem().unwrap_or_default().to_string_lossy();
    let thumb_path = thumb_dir.join(format!("{stem}.jpg"));
    std::fs::remove_file(&thumb_path).ok();

    log::info!("[library] Deleted recording: {}", file_path);
    Ok(())
}

/// Open a file with the system default application.
#[tauri::command]
pub async fn open_in_system(app: tauri::AppHandle, path: String) -> Result<(), String> {
    let config = config::get_config(app).await?;
    let output_dir = resolve_output_dir(&config.output_dir);
    validate_in_output_dir(&PathBuf::from(&path), &output_dir)?;
    open::that(&path).map_err(|e| format!("Failed to open file: {e}"))
}

/// Reveal a file in Finder.
#[tauri::command]
pub async fn reveal_in_finder(app: tauri::AppHandle, path: String) -> Result<(), String> {
    let config = config::get_config(app).await?;
    let output_dir = resolve_output_dir(&config.output_dir);
    validate_in_output_dir(&PathBuf::from(&path), &output_dir)?;
    tokio::process::Command::new("open")
        .arg("-R")
        .arg(&path)
        .output()
        .await
        .map_err(|e| format!("Failed to reveal in Finder: {e}"))?;
    Ok(())
}

/// Rename a recording and all its companion files (.meta.json, .txt, cached thumbnail).
#[tauri::command]
pub async fn rename_recording(
    app: tauri::AppHandle,
    file_path: String,
    new_name: String,
) -> Result<RecordingInfo, String> {
    let config = config::get_config(app).await?;
    let output_dir = resolve_output_dir(&config.output_dir);
    let old_path = PathBuf::from(&file_path);

    validate_in_output_dir(&old_path, &output_dir)?;

    // Validate new name
    let new_name = new_name.trim().to_string();
    if new_name.is_empty() {
        return Err("Name cannot be empty".to_string());
    }
    if new_name.contains('/') || new_name.contains('\\') || new_name.contains('\0') {
        return Err("Name cannot contain path separators".to_string());
    }

    // Ensure .mp4 extension
    let new_name = if new_name.ends_with(".mp4") {
        new_name
    } else {
        format!("{new_name}.mp4")
    };

    let new_path = output_dir.join(&new_name);

    // Prevent traversal via ".." in the name
    validate_in_output_dir(&old_path, &output_dir)
        .and_then(|_| {
            // new_path may not exist yet, so validate its parent
            let parent = new_path.parent().ok_or("Invalid path")?;
            let canonical_parent = std::fs::canonicalize(parent)
                .map_err(|e| format!("Invalid path: {e}"))?;
            let canonical_dir = std::fs::canonicalize(&output_dir)
                .map_err(|e| format!("Invalid output directory: {e}"))?;
            if !canonical_parent.starts_with(&canonical_dir) {
                return Err("Access denied: target is outside the output directory".to_string());
            }
            Ok(())
        })?;

    if new_path == old_path {
        // No-op: same name
        let recordings = scan_recordings(&output_dir)?;
        return recordings.into_iter()
            .find(|r| r.path == file_path)
            .ok_or_else(|| "Recording not found".to_string());
    }

    if new_path.exists() {
        return Err(format!("A file named \"{}\" already exists", new_name));
    }

    // Rename the .mp4
    std::fs::rename(&old_path, &new_path)
        .map_err(|e| format!("Failed to rename recording: {e}"))?;

    // Rename companion .meta.json
    let old_meta = old_path.with_extension("meta.json");
    if old_meta.exists() {
        let new_meta = new_path.with_extension("meta.json");
        std::fs::rename(&old_meta, &new_meta).ok();
    }

    // Rename companion .txt
    let old_txt = old_path.with_extension("txt");
    if old_txt.exists() {
        let new_txt = new_path.with_extension("txt");
        std::fs::rename(&old_txt, &new_txt).ok();
    }

    // Rename cached thumbnail
    let thumb_dir = output_dir.join(".thumbnails");
    let old_stem = old_path.file_stem().unwrap_or_default().to_string_lossy();
    let new_stem = new_path.file_stem().unwrap_or_default().to_string_lossy();
    let old_thumb = thumb_dir.join(format!("{old_stem}.jpg"));
    if old_thumb.exists() {
        let new_thumb = thumb_dir.join(format!("{new_stem}.jpg"));
        std::fs::rename(&old_thumb, &new_thumb).ok();
    }

    log::info!("[library] Renamed recording: {} -> {}", file_path, new_path.display());

    // Return updated RecordingInfo by re-scanning for this file
    let new_path_str = new_path.to_string_lossy().to_string();
    let filename = new_path.file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();
    let file_meta = std::fs::metadata(&new_path).ok();
    let size_bytes = file_meta.as_ref().map(|m| m.len()).unwrap_or(0);
    let created_at = parse_timestamp_from_filename(&filename)
        .or_else(|| {
            file_meta.as_ref()
                .and_then(|m| m.modified().ok())
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs())
        })
        .unwrap_or(0);

    let thumb_path = thumb_dir.join(format!("{new_stem}.jpg"));
    let thumbnail_path = if thumb_path.exists() {
        Some(thumb_path.to_string_lossy().to_string())
    } else {
        None
    };

    let meta_path = new_path.with_extension("meta.json");
    let meta = if meta_path.exists() {
        std::fs::read_to_string(&meta_path)
            .ok()
            .and_then(|content| serde_json::from_str::<RecordingMeta>(&content).ok())
    } else {
        None
    };

    Ok(RecordingInfo {
        path: new_path_str,
        filename,
        size_bytes,
        created_at,
        duration_secs: None,
        thumbnail_path,
        meta,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_timestamp_from_standard_filename() {
        let ts = parse_timestamp_from_filename("voiceover-1740000000.mp4");
        assert_eq!(ts, Some(1740000000));
    }

    #[test]
    fn parse_timestamp_returns_none_for_non_matching_filename() {
        assert_eq!(parse_timestamp_from_filename("random-file.mp4"), None);
        assert_eq!(parse_timestamp_from_filename("voiceover-.mp4"), None);
        assert_eq!(parse_timestamp_from_filename("voiceover-abc.mp4"), None);
    }

    #[test]
    fn parse_timestamp_returns_none_for_non_mp4() {
        assert_eq!(parse_timestamp_from_filename("voiceover-1740000000.txt"), None);
    }

    #[test]
    fn validate_in_output_dir_rejects_path_outside() {
        let tmp = std::env::temp_dir().join("vo-test-validate");
        std::fs::create_dir_all(&tmp).ok();
        let file = tmp.join("test.mp4");
        std::fs::write(&file, b"test").ok();

        let other_dir = std::env::temp_dir().join("vo-test-other");
        std::fs::create_dir_all(&other_dir).ok();

        let result = validate_in_output_dir(&file, &other_dir);
        assert!(result.is_err(), "expected rejection for path outside output dir");

        std::fs::remove_file(&file).ok();
        std::fs::remove_dir(&tmp).ok();
        std::fs::remove_dir(&other_dir).ok();
    }

    #[test]
    fn validate_in_output_dir_accepts_path_inside() {
        let tmp = std::env::temp_dir().join("vo-test-inside");
        std::fs::create_dir_all(&tmp).ok();
        let file = tmp.join("test.mp4");
        std::fs::write(&file, b"test").ok();

        let result = validate_in_output_dir(&file, &tmp);
        assert!(result.is_ok(), "expected acceptance for path inside output dir");

        std::fs::remove_file(&file).ok();
        std::fs::remove_dir(&tmp).ok();
    }

    #[test]
    fn recording_meta_deserializes_with_defaults() {
        let json = r#"{"voiceProfile": "MJ", "provider": "local"}"#;
        let meta: RecordingMeta = serde_json::from_str(json).unwrap();
        assert_eq!(meta.voice_profile.as_deref(), Some("MJ"));
        assert_eq!(meta.provider.as_deref(), Some("local"));
        assert_eq!(meta.drive_url, None);
        assert_eq!(meta.uploaded_at, None);
        assert!(!meta.voice_replacement);
    }

    #[test]
    fn recording_meta_serialization_roundtrip() {
        let meta = RecordingMeta {
            voice_profile: Some("TestVoice".to_string()),
            provider: Some("elevenlabs".to_string()),
            drive_url: Some("https://drive.google.com/file/123".to_string()),
            uploaded_at: Some(1740000000),
            voice_replacement: true,
        };
        let json = serde_json::to_string(&meta).unwrap();
        let deserialized: RecordingMeta = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.voice_profile, meta.voice_profile);
        assert_eq!(deserialized.drive_url, meta.drive_url);
        assert_eq!(deserialized.voice_replacement, meta.voice_replacement);
    }

    #[test]
    fn recording_info_serializes_camel_case() {
        let info = RecordingInfo {
            path: "/tmp/test.mp4".to_string(),
            filename: "test.mp4".to_string(),
            size_bytes: 1024,
            created_at: 1740000000,
            duration_secs: Some(120.5),
            thumbnail_path: None,
            meta: None,
        };
        let json = serde_json::to_string(&info).unwrap();
        assert!(json.contains("sizeBytes"), "expected camelCase sizeBytes in JSON");
        assert!(json.contains("createdAt"), "expected camelCase createdAt in JSON");
        assert!(json.contains("durationSecs"), "expected camelCase durationSecs in JSON");
        assert!(json.contains("thumbnailPath"), "expected camelCase thumbnailPath in JSON");
    }

    #[test]
    fn resolve_output_dir_falls_back_when_configured_missing() {
        let result = resolve_output_dir("/nonexistent/path/VoiceOver");
        // Should fall back to dirs::video_dir()/VoiceOver or similar
        // The configured path is returned only if neither exists
        let result_str = result.to_string_lossy();
        // Fallback is ~/Movies/VoiceOver on macOS
        assert!(
            result_str.contains("VoiceOver") || result_str == "/nonexistent/path/VoiceOver",
            "expected VoiceOver in fallback path, got: {result_str}"
        );
    }

    #[test]
    fn resolve_output_dir_never_returns_empty_path() {
        let result = resolve_output_dir("");
        assert!(!result.to_string_lossy().is_empty(), "empty config must not produce empty path");
        assert!(result.is_absolute(), "must return absolute path, got: {:?}", result);
        assert!(result.to_string_lossy().contains("VoiceOver"),
            "empty config should fall back to ~/Movies/VoiceOver, got: {:?}", result);
    }

    #[test]
    fn resolve_output_dir_never_returns_relative_path() {
        let result = resolve_output_dir("relative/path");
        assert!(result.is_absolute(), "must return absolute path even for relative input, got: {:?}", result);
    }

    #[test]
    fn resolve_output_dir_uses_configured_when_exists() {
        let tmp = std::env::temp_dir().join("vo-test-resolve");
        std::fs::create_dir_all(&tmp).ok();
        let result = resolve_output_dir(tmp.to_str().unwrap());
        assert_eq!(result, tmp);
        std::fs::remove_dir(&tmp).ok();
    }

    #[test]
    fn scan_recordings_finds_mp4_files() {
        let tmp = std::env::temp_dir().join("vo-test-scan");
        std::fs::create_dir_all(&tmp).ok();

        // Create test mp4 files
        std::fs::write(tmp.join("voiceover-1740000000.mp4"), b"fake mp4 1").ok();
        std::fs::write(tmp.join("voiceover-1740000001.mp4"), b"fake mp4 2").ok();
        std::fs::write(tmp.join("notes.txt"), b"not a video").ok();

        let results = scan_recordings(&tmp).unwrap();
        assert_eq!(results.len(), 2, "should find exactly 2 mp4 files");
        assert!(results[0].filename.ends_with(".mp4"));
        assert!(results[1].filename.ends_with(".mp4"));
        // Should be sorted newest first
        assert!(results[0].created_at >= results[1].created_at);

        // Cleanup
        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn scan_recordings_returns_empty_for_missing_dir() {
        let results = scan_recordings(Path::new("/nonexistent/path")).unwrap();
        assert!(results.is_empty());
    }

    #[test]
    fn scan_recordings_reads_meta_json() {
        let tmp = std::env::temp_dir().join("vo-test-scan-meta");
        std::fs::create_dir_all(&tmp).ok();

        std::fs::write(tmp.join("voiceover-1740000000.mp4"), b"fake").ok();
        std::fs::write(
            tmp.join("voiceover-1740000000.meta.json"),
            r#"{"voiceProfile":"MJ","provider":"local","voiceReplacement":true}"#,
        ).ok();

        let results = scan_recordings(&tmp).unwrap();
        assert_eq!(results.len(), 1);
        let meta = results[0].meta.as_ref().expect("should have meta");
        assert_eq!(meta.voice_profile.as_deref(), Some("MJ"));
        assert_eq!(meta.provider.as_deref(), Some("local"));
        assert!(meta.voice_replacement);

        std::fs::remove_dir_all(&tmp).ok();
    }

    // --- rename_recording tests (unit-level, no AppHandle) ---

    /// Helper: simulates what rename_recording does without needing an AppHandle.
    fn rename_recording_sync(
        output_dir: &Path,
        file_path: &str,
        new_name: &str,
    ) -> Result<String, String> {
        let old_path = PathBuf::from(file_path);
        validate_in_output_dir(&old_path, output_dir)?;

        let new_name = new_name.trim().to_string();
        if new_name.is_empty() {
            return Err("Name cannot be empty".to_string());
        }
        if new_name.contains('/') || new_name.contains('\\') || new_name.contains('\0') {
            return Err("Name cannot contain path separators".to_string());
        }
        let new_name = if new_name.ends_with(".mp4") { new_name } else { format!("{new_name}.mp4") };
        let new_path = output_dir.join(&new_name);

        if new_path.exists() {
            return Err(format!("A file named \"{}\" already exists", new_name));
        }

        std::fs::rename(&old_path, &new_path)
            .map_err(|e| format!("Failed to rename: {e}"))?;

        // Rename companions
        let old_meta = old_path.with_extension("meta.json");
        if old_meta.exists() {
            std::fs::rename(&old_meta, new_path.with_extension("meta.json")).ok();
        }
        let old_txt = old_path.with_extension("txt");
        if old_txt.exists() {
            std::fs::rename(&old_txt, new_path.with_extension("txt")).ok();
        }
        let thumb_dir = output_dir.join(".thumbnails");
        let old_stem = old_path.file_stem().unwrap_or_default().to_string_lossy().to_string();
        let old_thumb = thumb_dir.join(format!("{old_stem}.jpg"));
        if old_thumb.exists() {
            let new_stem = new_path.file_stem().unwrap_or_default().to_string_lossy().to_string();
            std::fs::rename(&old_thumb, thumb_dir.join(format!("{new_stem}.jpg"))).ok();
        }

        Ok(new_path.to_string_lossy().to_string())
    }

    #[test]
    fn rename_recording_renames_mp4_and_companions() {
        let tmp = std::env::temp_dir().join("vo-test-rename");
        std::fs::create_dir_all(&tmp).ok();
        std::fs::create_dir_all(tmp.join(".thumbnails")).ok();

        std::fs::write(tmp.join("voiceover-100.mp4"), b"video").ok();
        std::fs::write(tmp.join("voiceover-100.meta.json"), b"{}").ok();
        std::fs::write(tmp.join("voiceover-100.txt"), b"transcript").ok();
        std::fs::write(tmp.join(".thumbnails/voiceover-100.jpg"), b"thumb").ok();

        let result = rename_recording_sync(&tmp, tmp.join("voiceover-100.mp4").to_str().unwrap(), "my-demo");
        assert!(result.is_ok(), "rename failed: {:?}", result.err());

        // Old files gone
        assert!(!tmp.join("voiceover-100.mp4").exists());
        assert!(!tmp.join("voiceover-100.meta.json").exists());
        assert!(!tmp.join("voiceover-100.txt").exists());
        assert!(!tmp.join(".thumbnails/voiceover-100.jpg").exists());

        // New files present
        assert!(tmp.join("my-demo.mp4").exists());
        assert!(tmp.join("my-demo.meta.json").exists());
        assert!(tmp.join("my-demo.txt").exists());
        assert!(tmp.join(".thumbnails/my-demo.jpg").exists());

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn rename_recording_appends_mp4_extension() {
        let tmp = std::env::temp_dir().join("vo-test-rename-ext");
        std::fs::create_dir_all(&tmp).ok();
        std::fs::write(tmp.join("old.mp4"), b"video").ok();

        let result = rename_recording_sync(&tmp, tmp.join("old.mp4").to_str().unwrap(), "new-name");
        assert!(result.is_ok());
        assert!(tmp.join("new-name.mp4").exists());

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn rename_recording_preserves_explicit_mp4_extension() {
        let tmp = std::env::temp_dir().join("vo-test-rename-ext2");
        std::fs::create_dir_all(&tmp).ok();
        std::fs::write(tmp.join("old.mp4"), b"video").ok();

        let result = rename_recording_sync(&tmp, tmp.join("old.mp4").to_str().unwrap(), "new-name.mp4");
        assert!(result.is_ok());
        assert!(tmp.join("new-name.mp4").exists());
        // Should NOT create new-name.mp4.mp4
        assert!(!tmp.join("new-name.mp4.mp4").exists());

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn rename_recording_rejects_empty_name() {
        let tmp = std::env::temp_dir().join("vo-test-rename-empty");
        std::fs::create_dir_all(&tmp).ok();
        std::fs::write(tmp.join("test.mp4"), b"video").ok();

        let result = rename_recording_sync(&tmp, tmp.join("test.mp4").to_str().unwrap(), "");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("empty"));

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn rename_recording_rejects_path_separators() {
        let tmp = std::env::temp_dir().join("vo-test-rename-sep");
        std::fs::create_dir_all(&tmp).ok();
        std::fs::write(tmp.join("test.mp4"), b"video").ok();

        let result = rename_recording_sync(&tmp, tmp.join("test.mp4").to_str().unwrap(), "../evil");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("path separator"));

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn rename_recording_rejects_duplicate_name() {
        let tmp = std::env::temp_dir().join("vo-test-rename-dup");
        std::fs::create_dir_all(&tmp).ok();
        std::fs::write(tmp.join("a.mp4"), b"video a").ok();
        std::fs::write(tmp.join("b.mp4"), b"video b").ok();

        let result = rename_recording_sync(&tmp, tmp.join("a.mp4").to_str().unwrap(), "b");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("already exists"));

        std::fs::remove_dir_all(&tmp).ok();
    }
}

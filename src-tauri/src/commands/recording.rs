use std::fs;
use std::io::Write;
use std::path::PathBuf;

/// Validate that a session_id contains only safe characters (alphanumeric, hyphens, underscores).
fn validate_session_id(session_id: &str) -> Result<(), String> {
    if session_id.is_empty() {
        return Err("session_id must not be empty".to_string());
    }
    if !session_id.chars().all(|c| c.is_alphanumeric() || c == '-' || c == '_') {
        return Err("session_id contains invalid characters (only alphanumeric, hyphens, and underscores allowed)".to_string());
    }
    Ok(())
}

fn temp_recording_dir() -> PathBuf {
    let dir = std::env::temp_dir().join("voiceover-recordings");
    fs::create_dir_all(&dir).ok();
    dir
}

#[tauri::command]
pub fn get_temp_dir() -> String {
    temp_recording_dir().to_string_lossy().to_string()
}

/// Save a chunk of recording data (base64-encoded) to a temp file.
#[tauri::command]
pub fn save_recording_chunk(session_id: String, chunk: Vec<u8>, chunk_index: u32) -> Result<String, String> {
    validate_session_id(&session_id)?;
    let dir = temp_recording_dir().join(&session_id);
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;

    let chunk_path = dir.join(format!("chunk_{:04}.webm", chunk_index));
    let mut file = fs::File::create(&chunk_path).map_err(|e| e.to_string())?;
    file.write_all(&chunk).map_err(|e| e.to_string())?;

    Ok(chunk_path.to_string_lossy().to_string())
}

/// Read a file as raw bytes (used for video preview in webview).
/// Restricted to temp recording dir, video dir, and ~/VoiceOver for security.
#[tauri::command]
pub fn read_file_bytes(path: String) -> Result<Vec<u8>, String> {
    let requested = std::fs::canonicalize(&path)
        .map_err(|e| format!("Invalid path: {e}"))?;

    // Canonicalize allowlist dirs too so symlinks match consistently
    let temp_dir = std::fs::canonicalize(std::env::temp_dir()).unwrap_or_else(|_| std::env::temp_dir());
    let home_dir = dirs::home_dir()
        .ok_or_else(|| "Cannot determine home directory".to_string())?;
    let home_canon = std::fs::canonicalize(&home_dir).unwrap_or_else(|_| home_dir.clone());
    let video_dir = std::fs::canonicalize(dirs::video_dir().unwrap_or_else(|| home_dir.join("Videos")))
        .unwrap_or_else(|_| home_dir.join("Videos"));

    let allowed = requested.starts_with(&temp_dir)
        || requested.starts_with(&video_dir)
        || requested.starts_with(home_canon.join("VoiceOver"));

    if !allowed {
        return Err("Access denied: path outside allowed directories".to_string());
    }

    fs::read(&requested).map_err(|e| format!("Failed to read: {e}"))
}

/// Finalize a recording session by concatenating all chunks into a single file.
/// MediaRecorder chunks are WebM fragments (not standalone files) — byte append is correct.
#[tauri::command]
pub fn finalize_recording(session_id: String) -> Result<String, String> {
    validate_session_id(&session_id)?;
    let dir = temp_recording_dir().join(&session_id);
    let output_path = temp_recording_dir().join(format!("{session_id}.webm"));

    if !dir.exists() {
        return Err("No recording data — stopped too quickly".to_string());
    }

    let mut chunks: Vec<PathBuf> = fs::read_dir(&dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|ext| ext == "webm"))
        .collect();

    if chunks.is_empty() {
        fs::remove_dir_all(&dir).ok();
        return Err("No recording data — stopped too quickly".to_string());
    }

    chunks.sort();

    let mut output = fs::File::create(&output_path).map_err(|e| e.to_string())?;
    for chunk in &chunks {
        let data = fs::read(chunk).map_err(|e| e.to_string())?;
        output.write_all(&data).map_err(|e| e.to_string())?;
    }

    // Clean up chunk directory
    fs::remove_dir_all(&dir).ok();

    Ok(output_path.to_string_lossy().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid_session_id_with_alphanumeric_hyphens_underscores() {
        assert!(validate_session_id("rec-1234567890-abc123").is_ok());
    }

    #[test]
    fn valid_session_id_with_underscores() {
        assert!(validate_session_id("my_session_id").is_ok());
    }

    #[test]
    fn empty_session_id_is_rejected() {
        let err = validate_session_id("").unwrap_err();
        assert!(err.contains("empty"), "expected 'empty' in error: {err}");
    }

    #[test]
    fn session_id_with_path_traversal_is_rejected() {
        assert!(validate_session_id("../../etc/passwd").is_err());
    }

    #[test]
    fn session_id_with_slashes_is_rejected() {
        assert!(validate_session_id("session/evil").is_err());
    }

    #[test]
    fn session_id_with_spaces_is_rejected() {
        assert!(validate_session_id("session id").is_err());
    }

    #[test]
    fn session_id_with_dots_is_rejected() {
        assert!(validate_session_id("session.id").is_err());
    }

    #[test]
    fn temp_recording_dir_is_under_system_temp() {
        let dir = temp_recording_dir();
        let tmp = std::env::temp_dir();
        assert!(
            dir.starts_with(&tmp),
            "expected {dir:?} to start with {tmp:?}"
        );
        assert!(
            dir.to_string_lossy().contains("voiceover-recordings"),
            "expected 'voiceover-recordings' in {dir:?}"
        );
    }

    #[test]
    fn save_and_finalize_roundtrip() {
        let session_id = format!("test-session-{}", std::process::id());

        // Save 3 chunks
        save_recording_chunk(session_id.clone(), vec![1, 2, 3], 0).unwrap();
        save_recording_chunk(session_id.clone(), vec![4, 5, 6], 1).unwrap();
        save_recording_chunk(session_id.clone(), vec![7, 8, 9], 2).unwrap();

        // Finalize
        let output_path = finalize_recording(session_id.clone()).unwrap();
        let output = PathBuf::from(&output_path);

        // Verify concatenated content
        let data = fs::read(&output).unwrap();
        assert_eq!(data, vec![1, 2, 3, 4, 5, 6, 7, 8, 9]);

        // Verify chunk dir was cleaned up
        let chunk_dir = temp_recording_dir().join(&session_id);
        assert!(!chunk_dir.exists(), "chunk dir should be cleaned up");

        // Clean up test artifact
        fs::remove_file(&output).ok();
    }

    /// Guard: finalize must produce exact byte-concat of all chunks, preserving every byte.
    /// MediaRecorder WebM fragments depend on byte continuity — any reprocessing (e.g. ffmpeg
    /// concat demuxer) would break the stream because chunks after the first lack EBML headers.
    #[test]
    fn finalize_preserves_all_chunk_bytes_in_order() {
        let session_id = format!("test-byteconcat-{}", std::process::id());

        // Simulate realistic chunk sizes with recognizable patterns
        let chunk_0: Vec<u8> = (0..=255).collect(); // 256 bytes: EBML header + init
        let chunk_1: Vec<u8> = vec![0xCA; 512];      // 512 bytes: cluster data
        let chunk_2: Vec<u8> = vec![0xFE; 128];      // 128 bytes: cluster data

        save_recording_chunk(session_id.clone(), chunk_0.clone(), 0).unwrap();
        save_recording_chunk(session_id.clone(), chunk_1.clone(), 1).unwrap();
        save_recording_chunk(session_id.clone(), chunk_2.clone(), 2).unwrap();

        let output_path = finalize_recording(session_id.clone()).unwrap();
        let result = fs::read(&output_path).unwrap();

        // Total size must equal sum of all chunks (no bytes lost or added)
        assert_eq!(
            result.len(),
            chunk_0.len() + chunk_1.len() + chunk_2.len(),
            "finalize must not drop or add bytes — got {} expected {}",
            result.len(),
            chunk_0.len() + chunk_1.len() + chunk_2.len()
        );

        // Byte-exact match: chunks must appear in order without modification
        let mut expected = Vec::new();
        expected.extend_from_slice(&chunk_0);
        expected.extend_from_slice(&chunk_1);
        expected.extend_from_slice(&chunk_2);
        assert_eq!(result, expected, "finalize must byte-concat chunks in order");

        fs::remove_file(&output_path).ok();
    }
}

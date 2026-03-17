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

/// Finalize a recording session by concatenating all chunks into a single file.
#[tauri::command]
pub fn finalize_recording(session_id: String) -> Result<String, String> {
    validate_session_id(&session_id)?;
    let dir = temp_recording_dir().join(&session_id);
    let output_path = temp_recording_dir().join(format!("{session_id}.webm"));

    let mut chunks: Vec<PathBuf> = fs::read_dir(&dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().map_or(false, |ext| ext == "webm"))
        .collect();

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

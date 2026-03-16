use std::path::Path;
use std::process::Command;

/// Extract audio from a video file as 16kHz mono WAV (optimal for ElevenLabs S2S).
pub fn extract_audio(input_video: &Path, output_wav: &Path) -> Result<(), String> {
    let status = Command::new("ffmpeg")
        .args([
            "-y",
            "-i",
            input_video.to_str().unwrap(),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_wav.to_str().unwrap(),
        ])
        .output()
        .map_err(|e| format!("Failed to run ffmpeg: {e}"))?;

    if !status.status.success() {
        let stderr = String::from_utf8_lossy(&status.stderr);
        return Err(format!("ffmpeg extract audio failed: {stderr}"));
    }
    Ok(())
}

/// Replace the audio track in a video file with new audio.
/// Uses `-c:v copy` to avoid re-encoding video (fast).
pub fn replace_audio(
    input_video: &Path,
    new_audio: &Path,
    output_mp4: &Path,
) -> Result<(), String> {
    let status = Command::new("ffmpeg")
        .args([
            "-y",
            "-i",
            input_video.to_str().unwrap(),
            "-i",
            new_audio.to_str().unwrap(),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            output_mp4.to_str().unwrap(),
        ])
        .output()
        .map_err(|e| format!("Failed to run ffmpeg: {e}"))?;

    if !status.status.success() {
        let stderr = String::from_utf8_lossy(&status.stderr);
        return Err(format!("ffmpeg replace audio failed: {stderr}"));
    }
    Ok(())
}

/// Normalize a recording to MP4 format (handles platform codec differences).
pub fn normalize_to_mp4(input: &Path, output_mp4: &Path) -> Result<(), String> {
    let status = Command::new("ffmpeg")
        .args([
            "-y",
            "-i",
            input.to_str().unwrap(),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            output_mp4.to_str().unwrap(),
        ])
        .output()
        .map_err(|e| format!("Failed to run ffmpeg: {e}"))?;

    if !status.status.success() {
        let stderr = String::from_utf8_lossy(&status.stderr);
        return Err(format!("ffmpeg normalize failed: {stderr}"));
    }
    Ok(())
}

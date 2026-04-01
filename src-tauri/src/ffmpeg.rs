use std::path::{Path, PathBuf};
use tokio::process::Command;

/// Resolve the ffmpeg binary path.
/// In a bundled .app, the sidecar lives next to the main executable in Contents/MacOS/.
/// Falls back to "ffmpeg" on the system PATH for development.
pub fn resolve_ffmpeg_path() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        let sidecar = exe.parent().unwrap_or(Path::new(".")).join("ffmpeg");
        if sidecar.exists() {
            log::info!("[ffmpeg] Using bundled binary: {:?}", sidecar);
            return sidecar;
        }
    }
    log::info!("[ffmpeg] Using system PATH ffmpeg");
    PathBuf::from("ffmpeg")
}

/// Build ffmpeg arguments for audio extraction.
pub(crate) fn extract_audio_args(input: &str, output: &str) -> Vec<String> {
    ["-y", "-i", input, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Build ffmpeg arguments for audio replacement.
pub(crate) fn replace_audio_args(input_video: &str, new_audio: &str, output: &str) -> Vec<String> {
    ["-y", "-i", input_video, "-i", new_audio, "-map", "0:v", "-map", "1:a",
     "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-preset", "fast",
     "-c:a", "aac", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Build ffmpeg arguments for MP4 normalization.
pub(crate) fn normalize_args(input: &str, output: &str) -> Vec<String> {
    ["-y", "-i", input, "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
     "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Extract audio from a video file as 16kHz mono WAV (optimal for ElevenLabs S2S).
pub async fn extract_audio(input_video: &Path, output_wav: &Path) -> Result<(), String> {
    let args = extract_audio_args(
        input_video.to_str().unwrap(),
        output_wav.to_str().unwrap(),
    );
    let status = Command::new(resolve_ffmpeg_path())
        .args(&args)
        .output()
        .await
        .map_err(|e| format!("Failed to run ffmpeg: {e}"))?;

    if !status.status.success() {
        let stderr = String::from_utf8_lossy(&status.stderr);
        return Err(format!("ffmpeg extract audio failed: {stderr}"));
    }
    Ok(())
}

/// Replace the audio track in a video file with new audio.
/// Re-encodes video to H.264 (input may be VP8/WebM which can't mux into MP4).
pub async fn replace_audio(
    input_video: &Path,
    new_audio: &Path,
    output_mp4: &Path,
) -> Result<(), String> {
    let args = replace_audio_args(
        input_video.to_str().unwrap(),
        new_audio.to_str().unwrap(),
        output_mp4.to_str().unwrap(),
    );
    let status = Command::new(resolve_ffmpeg_path())
        .args(&args)
        .output()
        .await
        .map_err(|e| format!("Failed to run ffmpeg: {e}"))?;

    if !status.status.success() {
        let stderr = String::from_utf8_lossy(&status.stderr);
        return Err(format!("ffmpeg replace audio failed: {stderr}"));
    }
    Ok(())
}

/// Probe the duration of a media file using ffprobe (falls back to ffmpeg -i).
/// Returns duration in seconds, or an error if it can't be determined.
pub async fn probe_duration(input: &Path) -> Result<f64, String> {
    let input_str = input.to_str()
        .ok_or_else(|| "Path contains non-UTF8 characters".to_string())?;

    // Try ffprobe first (more reliable for WebM containers)
    let ffprobe_path = resolve_ffmpeg_path()
        .parent()
        .unwrap_or(Path::new("."))
        .join("ffprobe");
    let ffprobe_bin = if ffprobe_path.exists() {
        ffprobe_path
    } else {
        PathBuf::from("ffprobe")
    };

    let output = Command::new(&ffprobe_bin)
        .args([
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "csv=p=0",
            input_str,
        ])
        .output()
        .await;

    if let Ok(out) = output {
        let stdout = String::from_utf8_lossy(&out.stdout);
        if let Ok(dur) = stdout.trim().parse::<f64>() {
            if dur > 0.0 {
                return Ok(dur);
            }
        }
    }

    // Fallback: use ffmpeg to decode and count frames (slower but works for WebM without duration)
    let output = Command::new(resolve_ffmpeg_path())
        .args([
            "-i", input_str,
            "-f", "null", "-",
        ])
        .output()
        .await
        .map_err(|e| format!("Failed to probe duration: {e}"))?;

    // ffmpeg prints "Duration: HH:MM:SS.ms" or "time=HH:MM:SS.ms" in stderr
    let stderr = String::from_utf8_lossy(&output.stderr);
    // Parse the last "time=" value (most accurate for variable-rate streams)
    for line in stderr.lines().rev() {
        if let Some(pos) = line.find("time=") {
            let time_str = &line[pos + 5..];
            if let Some(end) = time_str.find([' ', '\n']) {
                if let Ok(dur) = parse_ffmpeg_time(&time_str[..end]) {
                    return Ok(dur);
                }
            } else if let Ok(dur) = parse_ffmpeg_time(time_str.trim()) {
                return Ok(dur);
            }
        }
    }

    Err("Could not determine media duration".to_string())
}

/// Parse HH:MM:SS.ms format to seconds.
fn parse_ffmpeg_time(time_str: &str) -> Result<f64, String> {
    let parts: Vec<&str> = time_str.split(':').collect();
    if parts.len() != 3 {
        return Err(format!("Invalid time format: {time_str}"));
    }
    let hours: f64 = parts[0].parse().map_err(|_| "bad hours")?;
    let minutes: f64 = parts[1].parse().map_err(|_| "bad minutes")?;
    let seconds: f64 = parts[2].parse().map_err(|_| "bad seconds")?;
    Ok(hours * 3600.0 + minutes * 60.0 + seconds)
}

/// Normalize a recording to MP4 format (handles platform codec differences).
pub async fn normalize_to_mp4(input: &Path, output_mp4: &Path) -> Result<(), String> {
    let args = normalize_args(
        input.to_str().unwrap(),
        output_mp4.to_str().unwrap(),
    );
    let status = Command::new(resolve_ffmpeg_path())
        .args(&args)
        .output()
        .await
        .map_err(|e| format!("Failed to run ffmpeg: {e}"))?;

    if !status.status.success() {
        let stderr = String::from_utf8_lossy(&status.stderr);
        return Err(format!("ffmpeg normalize failed: {stderr}"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_audio_args_use_16khz_mono_pcm() {
        let args = extract_audio_args("input.webm", "output.wav");
        assert!(args.contains(&"-ar".to_string()));
        assert!(args.contains(&"16000".to_string()));
        assert!(args.contains(&"-ac".to_string()));
        assert!(args.contains(&"1".to_string()));
        assert!(args.contains(&"pcm_s16le".to_string()));
    }

    #[test]
    fn extract_audio_args_strip_video() {
        let args = extract_audio_args("input.webm", "output.wav");
        assert!(args.contains(&"-vn".to_string()));
    }

    #[test]
    fn replace_audio_args_map_video_from_first_audio_from_second() {
        let args = replace_audio_args("video.webm", "audio.mp3", "output.mp4");
        // Find both -map args
        let map_indices: Vec<usize> = args.iter().enumerate()
            .filter(|(_, a)| a.as_str() == "-map")
            .map(|(i, _)| i)
            .collect();
        assert_eq!(map_indices.len(), 2, "expected 2 -map flags");
        assert_eq!(args[map_indices[0] + 1], "0:v");
        assert_eq!(args[map_indices[1] + 1], "1:a");
    }

    #[test]
    fn replace_audio_args_use_h264_and_aac() {
        let args = replace_audio_args("video.webm", "audio.mp3", "output.mp4");
        assert!(args.contains(&"libx264".to_string()));
        assert!(args.contains(&"aac".to_string()));
    }

    #[test]
    fn replace_audio_args_pad_to_even_dimensions() {
        let args = replace_audio_args("video.webm", "audio.mp3", "output.mp4");
        assert!(args.contains(&"pad=ceil(iw/2)*2:ceil(ih/2)*2".to_string()));
    }

    #[test]
    fn normalize_args_use_h264_aac_with_even_padding() {
        let args = normalize_args("input.webm", "output.mp4");
        assert!(args.contains(&"libx264".to_string()));
        assert!(args.contains(&"aac".to_string()));
        assert!(args.contains(&"pad=ceil(iw/2)*2:ceil(ih/2)*2".to_string()));
    }

    #[test]
    fn replace_audio_args_no_shortest_flag() {
        let args = replace_audio_args("video.webm", "audio.mp3", "output.mp4");
        assert!(
            !args.contains(&"-shortest".to_string()),
            "replace_audio_args must not use -shortest (audio should match video duration)"
        );
    }

    #[test]
    fn all_commands_use_overwrite_flag() {
        let extract = extract_audio_args("in.webm", "out.wav");
        let replace = replace_audio_args("in.webm", "audio.mp3", "out.mp4");
        let normalize = normalize_args("in.webm", "out.mp4");

        assert_eq!(extract[0], "-y", "extract_audio_args should start with -y");
        assert_eq!(replace[0], "-y", "replace_audio_args should start with -y");
        assert_eq!(normalize[0], "-y", "normalize_args should start with -y");
    }
}

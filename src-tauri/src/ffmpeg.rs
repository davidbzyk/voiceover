use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use tokio::process::Command;

/// 16kHz mono PCM — optimal for speech-to-speech APIs
const SPEECH_SAMPLE_RATE: &str = "16000";
const SPEECH_CHANNELS: &str = "1";
/// H.264 fast preset for screen recordings
const VIDEO_PRESET: &str = "fast";
/// 320px thumbnails for library grid
const THUMBNAIL_WIDTH: &str = "320";

static FFMPEG_PATH: OnceLock<PathBuf> = OnceLock::new();

/// Resolve the ffmpeg binary path (cached after first call).
/// In a bundled .app, the sidecar lives next to the main executable in Contents/MacOS/.
/// Falls back to "ffmpeg" on the system PATH for development.
pub fn resolve_ffmpeg_path() -> &'static Path {
    FFMPEG_PATH
        .get_or_init(|| {
            if let Ok(exe) = std::env::current_exe() {
                let sidecar = exe.parent().unwrap_or(Path::new(".")).join("ffmpeg");
                if sidecar.exists() {
                    log::info!("[ffmpeg] Using bundled binary: {:?}", sidecar);
                    return sidecar;
                }
            }
            log::info!("[ffmpeg] Using system PATH ffmpeg");
            PathBuf::from("ffmpeg")
        })
        .as_path()
}

/// Build ffmpeg arguments for audio extraction.
pub(crate) fn extract_audio_args(input: &str, output: &str) -> Vec<String> {
    ["-y", "-i", input, "-vn", "-acodec", "pcm_s16le", "-ar", SPEECH_SAMPLE_RATE, "-ac", SPEECH_CHANNELS, output]
        .iter().map(|s| s.to_string()).collect()
}

/// Build ffmpeg arguments for audio replacement.
pub(crate) fn replace_audio_args(input_video: &str, new_audio: &str, output: &str) -> Vec<String> {
    let video_codec = if cfg!(target_os = "macos") { "h264_videotoolbox" } else { "libx264" };
    ["-y", "-i", input_video, "-i", new_audio, "-map", "0:v", "-map", "1:a",
     "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", video_codec, "-preset", VIDEO_PRESET,
     "-c:a", "aac", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Build ffmpeg arguments for MP4 normalization.
pub(crate) fn normalize_args(input: &str, output: &str) -> Vec<String> {
    let video_codec = if cfg!(target_os = "macos") { "h264_videotoolbox" } else { "libx264" };
    ["-y", "-i", input, "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
     "-c:v", video_codec, "-preset", VIDEO_PRESET, "-c:a", "aac", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Extract audio from a video file as 16kHz mono WAV (optimal for ElevenLabs S2S).
pub async fn extract_audio(input_video: &Path, output_wav: &Path) -> Result<(), String> {
    let args = extract_audio_args(
        input_video.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
        output_wav.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
    );
    run_ffmpeg(&args, "extract audio").await
}

/// Replace the audio track in a video file with new audio.
/// Re-encodes video to H.264 (input may be VP8/WebM which can't mux into MP4).
pub async fn replace_audio(
    input_video: &Path,
    new_audio: &Path,
    output_mp4: &Path,
) -> Result<(), String> {
    let args = replace_audio_args(
        input_video.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
        new_audio.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
        output_mp4.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
    );
    run_ffmpeg(&args, "replace audio").await
}

/// Run ffmpeg with `args`, returning stderr in the error when it fails.
async fn run_ffmpeg(args: &[String], context: &str) -> Result<(), String> {
    let output = Command::new(resolve_ffmpeg_path())
        .args(args)
        .output()
        .await
        .map_err(|e| format!("Failed to run ffmpeg: {e}"))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("ffmpeg {context} failed: {stderr}"));
    }
    Ok(())
}

/// Convert a path to &str for ffmpeg arguments.
fn path_arg(path: &Path) -> Result<&str, String> {
    path.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())
}

/// Build ffmpeg arguments that keep a recording's own voice as AAC, for converting it again later.
pub(crate) fn keep_original_voice_args(input: &str, output: &str) -> Vec<String> {
    ["-y", "-i", input, "-vn", "-c:a", "aac", "-b:a", "128k", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Save the audio track of `input` as `output` (.m4a).
pub async fn keep_original_voice(input: &Path, output: &Path) -> Result<(), String> {
    run_ffmpeg(&keep_original_voice_args(path_arg(input)?, path_arg(output)?), "keep original voice").await
}

/// Build ffmpeg arguments that swap an mp4's audio without re-encoding its video.
pub(crate) fn swap_audio_args(video: &str, new_audio: &str, output: &str) -> Vec<String> {
    // The output is staged under a non-.mp4 name, so the format cannot be inferred from it.
    ["-y", "-i", video, "-i", new_audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-f", "mp4", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Replace the audio of an existing mp4, copying its video stream as is.
pub async fn swap_audio(video: &Path, new_audio: &Path, output_mp4: &Path) -> Result<(), String> {
    run_ffmpeg(&swap_audio_args(path_arg(video)?, path_arg(new_audio)?, path_arg(output_mp4)?), "swap audio").await
}

/// Build ffmpeg arguments that join audio pieces, padding or trimming each to its exact source length.
pub(crate) fn concat_exact_args(pieces: &[(String, f64)], output: &str) -> Vec<String> {
    let mut args = vec!["-y".to_string()];
    for (path, _) in pieces {
        args.push("-i".to_string());
        args.push(path.clone());
    }
    let mut filter = String::new();
    for (i, (_, secs)) in pieces.iter().enumerate() {
        filter.push_str(&format!("[{i}:a]aresample=44100,apad,atrim=end={secs:.6}[a{i}];"));
    }
    for i in 0..pieces.len() {
        filter.push_str(&format!("[a{i}]"));
    }
    filter.push_str(&format!("concat=n={}:v=0:a=1[out]", pieces.len()));
    args.extend(["-filter_complex".to_string(), filter, "-map".to_string(), "[out]".to_string(), output.to_string()]);
    args
}

/// Join converted pieces into one track whose length equals the sum of the source pieces.
pub async fn concat_exact(pieces: &[(std::path::PathBuf, f64)], output: &Path) -> Result<(), String> {
    let pieces = pieces
        .iter()
        .map(|(p, secs)| Ok((path_arg(p)?.to_string(), *secs)))
        .collect::<Result<Vec<_>, String>>()?;
    run_ffmpeg(&concat_exact_args(&pieces, path_arg(output)?), "concat").await
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

    // Try video stream duration first
    let mut best_duration: f64 = 0.0;

    let stream_output = Command::new(&ffprobe_bin)
        .args([
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "csv=p=0",
            input_str,
        ])
        .output()
        .await;

    if let Ok(out) = stream_output {
        let stdout = String::from_utf8_lossy(&out.stdout);
        if let Ok(dur) = stdout.trim().parse::<f64>() {
            if dur > 0.0 {
                log::info!("[ffmpeg] ffprobe video stream duration: {:.2}s", dur);
                best_duration = dur;
            }
        }
    }

    // Also try format/container duration (WebM often lacks per-stream duration
    // but has a container-level Duration field)
    let format_output = Command::new(&ffprobe_bin)
        .args([
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            input_str,
        ])
        .output()
        .await;

    if let Ok(out) = format_output {
        let stdout = String::from_utf8_lossy(&out.stdout);
        if let Ok(dur) = stdout.trim().parse::<f64>() {
            if dur > best_duration {
                log::info!("[ffmpeg] ffprobe format duration: {:.2}s (longer than stream: {:.2}s)", dur, best_duration);
                best_duration = dur;
            }
        }
    }

    if best_duration > 0.0 {
        return Ok(best_duration);
    }
    log::debug!("[ffmpeg] ffprobe returned no usable duration, falling back to ffmpeg decode");

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
        input.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
        output_mp4.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
    );
    run_ffmpeg(&args, "normalize").await
}

/// Build ffmpeg arguments for thumbnail extraction (first frame at 1s, 320px wide JPEG).
pub(crate) fn thumbnail_args(input: &str, output: &str) -> Vec<String> {
    let scale_filter = format!("scale={THUMBNAIL_WIDTH}:-1");
    ["-y", "-i", input, "-ss", "00:00:01", "-vframes", "1",
     "-vf", &scale_filter, "-q:v", "3", output]
        .iter().map(|s| s.to_string()).collect()
}

/// Extract a thumbnail JPEG from a video file.
pub async fn extract_thumbnail(input: &Path, output: &Path) -> Result<(), String> {
    let args = thumbnail_args(
        input.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
        output.to_str().ok_or_else(|| "Path contains non-UTF8 characters".to_string())?,
    );
    run_ffmpeg(&args, "thumbnail extraction").await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn swap_audio_args_copy_video_and_map_new_audio() {
        let args = swap_audio_args("in.mp4", "voice.wav", "out.mp4");
        let joined = args.join(" ");
        assert!(joined.contains("-map 0:v -map 1:a -c:v copy -c:a aac -f mp4"), "{joined}");
    }

    /// Make a 1s test video and a 1s tone with the real ffmpeg; None when ffmpeg is not installed.
    fn real_media(dir: &Path) -> Option<(PathBuf, PathBuf)> {
        let video = dir.join("in.mp4");
        let audio = dir.join("voice.wav");
        let ok = |args: &[&str]| std::process::Command::new(resolve_ffmpeg_path()).args(args).output().map(|o| o.status.success()).unwrap_or(false);
        let made = ok(&["-y", "-f", "lavfi", "-i", "testsrc=size=64x64:duration=1", "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-c:a", "aac", video.to_str()?])
            && ok(&["-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1", audio.to_str()?]);
        made.then_some((video, audio))
    }

    #[tokio::test]
    async fn swap_audio_writes_an_mp4_to_a_staging_name_without_an_mp4_extension() {
        let dir = std::env::temp_dir().join("vo-test-swap-audio");
        std::fs::remove_dir_all(&dir).ok();
        std::fs::create_dir_all(&dir).unwrap();
        let Some((video, audio)) = real_media(&dir) else {
            eprintln!("skipped: ffmpeg with lavfi/libx264 not available");
            return;
        };
        // Same shape as pipeline::staging_path: the reconvert stages to "<name>.mp4.part"
        let staged = dir.join("voiceover-1.mp4.part");
        let result = swap_audio(&video, &audio, &staged).await;
        assert!(result.is_ok(), "{result:?}");
        assert!(std::fs::metadata(&staged).map(|m| m.len() > 0).unwrap_or(false));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[tokio::test]
    async fn keep_original_voice_and_concat_exact_produce_files_with_real_ffmpeg() {
        let dir = std::env::temp_dir().join("vo-test-real-ffmpeg");
        std::fs::remove_dir_all(&dir).ok();
        std::fs::create_dir_all(&dir).unwrap();
        let Some((video, audio)) = real_media(&dir) else {
            eprintln!("skipped: ffmpeg with lavfi/libx264 not available");
            return;
        };
        let original = dir.join("voiceover-1.original.m4a");
        keep_original_voice(&video, &original).await.unwrap();
        assert!(std::fs::metadata(&original).map(|m| m.len() > 0).unwrap_or(false));

        let joined = dir.join("joined.wav");
        concat_exact(&[(audio.clone(), 0.75), (audio, 0.5)], &joined).await.unwrap();
        let secs = probe_duration(&joined).await.unwrap();
        assert!((secs - 1.25).abs() < 0.02, "joined length {secs}s, expected 1.25s");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn concat_exact_args_trim_each_piece_to_its_source_length() {
        let args = concat_exact_args(&[("a.mp3".into(), 280.25), ("b.mp3".into(), 130.08)], "out.wav");
        let filter = &args[args.iter().position(|a| a == "-filter_complex").unwrap() + 1];
        assert!(filter.contains("[0:a]aresample=44100,apad,atrim=end=280.250000[a0]"), "{filter}");
        assert!(filter.contains("[1:a]aresample=44100,apad,atrim=end=130.080000[a1]"), "{filter}");
        assert!(filter.ends_with("[a0][a1]concat=n=2:v=0:a=1[out]"), "{filter}");
    }

    #[test]
    fn keep_original_voice_args_drop_video_and_encode_aac() {
        let args = keep_original_voice_args("rec.webm", "rec.original.m4a").join(" ");
        assert!(args.contains("-vn -c:a aac"), "{args}");
    }

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
        let expected_codec = if cfg!(target_os = "macos") { "h264_videotoolbox" } else { "libx264" };
        assert!(args.contains(&expected_codec.to_string()));
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
        let expected_codec = if cfg!(target_os = "macos") { "h264_videotoolbox" } else { "libx264" };
        assert!(args.contains(&expected_codec.to_string()));
        assert!(args.contains(&"aac".to_string()));
        assert!(args.contains(&"pad=ceil(iw/2)*2:ceil(ih/2)*2".to_string()));
    }

    #[test]
    fn replace_audio_args_no_shortest_flag() {
        let args = replace_audio_args("video.webm", "audio.mp3", "output.mp4");
        assert!(
            !args.contains(&"-shortest".to_string()),
            "replace_audio_args must not use -shortest (audio is padded to video duration upstream)"
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

    #[test]
    fn parse_ffmpeg_time_valid_time() {
        let result = parse_ffmpeg_time("01:23:45.678").unwrap();
        let expected = 1.0 * 3600.0 + 23.0 * 60.0 + 45.678;
        assert!(
            (result - expected).abs() < 1e-6,
            "expected {expected}, got {result}"
        );
    }

    #[test]
    fn parse_ffmpeg_time_zero() {
        let result = parse_ffmpeg_time("00:00:00.00").unwrap();
        assert!(
            result.abs() < 1e-9,
            "expected 0.0, got {result}"
        );
    }

    #[test]
    fn parse_ffmpeg_time_small_value() {
        let result = parse_ffmpeg_time("00:00:00.001").unwrap();
        assert!(
            (result - 0.001).abs() < 1e-9,
            "expected 0.001, got {result}"
        );
    }

    #[test]
    fn parse_ffmpeg_time_invalid_input() {
        let result = parse_ffmpeg_time("not-a-time");
        assert!(result.is_err(), "expected Err for invalid input, got {result:?}");
    }

    #[test]
    fn parse_ffmpeg_time_wrong_format_too_few_parts() {
        let result = parse_ffmpeg_time("1:2");
        assert!(result.is_err(), "expected Err for wrong format, got {result:?}");
    }

    #[test]
    fn thumbnail_args_use_overwrite_flag() {
        let args = thumbnail_args("input.mp4", "output.jpg");
        assert_eq!(args[0], "-y", "thumbnail_args should start with -y");
    }

    #[test]
    fn thumbnail_args_seek_and_single_frame() {
        let args = thumbnail_args("input.mp4", "output.jpg");
        assert!(args.contains(&"-ss".to_string()));
        assert!(args.contains(&"00:00:01".to_string()));
        assert!(args.contains(&"-vframes".to_string()));
        assert!(args.contains(&"1".to_string()));
    }

    #[test]
    fn thumbnail_args_scale_width_320() {
        let args = thumbnail_args("input.mp4", "output.jpg");
        assert!(args.contains(&"scale=320:-1".to_string()));
    }
}

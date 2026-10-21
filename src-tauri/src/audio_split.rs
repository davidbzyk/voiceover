use std::path::Path;

/// 16-bit PCM mono audio as written by `ffmpeg::extract_audio`.
pub(crate) struct PcmAudio {
    pub samples: Vec<i16>,
    pub sample_rate: u32,
}

impl PcmAudio {
    /// Length in seconds.
    pub fn duration_secs(&self) -> f64 {
        self.samples.len() as f64 / self.sample_rate as f64
    }
}

/// Read a 16-bit PCM mono WAV, walking its chunks so extra header chunks (LIST, etc.) are skipped.
pub(crate) fn read_pcm16_mono(path: &Path) -> Result<PcmAudio, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("Failed to read {:?}: {e}", path))?;
    if bytes.len() < 12 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return Err(format!("{:?} is not a WAV file", path));
    }
    let mut pos = 12;
    let mut sample_rate = None;
    while pos + 8 <= bytes.len() {
        let id = &bytes[pos..pos + 4];
        let size = u32::from_le_bytes(bytes[pos + 4..pos + 8].try_into().unwrap()) as usize;
        let body = pos + 8;
        let end = (body + size).min(bytes.len());
        if id == b"fmt " && size >= 16 {
            if body + 16 > bytes.len() {
                return Err(format!("{:?} has a truncated fmt chunk", path));
            }
            let format = u16::from_le_bytes([bytes[body], bytes[body + 1]]);
            let channels = u16::from_le_bytes([bytes[body + 2], bytes[body + 3]]);
            let bits = u16::from_le_bytes([bytes[body + 14], bytes[body + 15]]);
            if format != 1 || channels != 1 || bits != 16 {
                return Err(format!("Expected 16-bit PCM mono WAV, got format={format} channels={channels} bits={bits}"));
            }
            sample_rate = Some(u32::from_le_bytes(
                bytes[body + 4..body + 8].try_into().unwrap(),
            ));
        } else if id == b"data" {
            let sample_rate = sample_rate.ok_or("WAV data chunk appears before fmt chunk")?;
            let samples = bytes[body..end]
                .chunks_exact(2)
                .map(|b| i16::from_le_bytes([b[0], b[1]]))
                .collect();
            return Ok(PcmAudio {
                samples,
                sample_rate,
            });
        }
        pos = body + size + (size & 1);
    }
    Err(format!("{:?} has no data chunk", path))
}

/// Write samples as a 16-bit PCM mono WAV.
pub(crate) fn write_pcm16_mono(
    path: &Path,
    samples: &[i16],
    sample_rate: u32,
) -> Result<(), String> {
    let data_len = (samples.len() * 2) as u32;
    let mut out = Vec::with_capacity(44 + data_len as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVEfmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&sample_rate.to_le_bytes());
    out.extend_from_slice(&(sample_rate * 2).to_le_bytes());
    out.extend_from_slice(&2u16.to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for s in samples {
        out.extend_from_slice(&s.to_le_bytes());
    }
    std::fs::write(path, out).map_err(|e| format!("Failed to write {:?}: {e}", path))
}

/// Choose cut points so no piece is longer than `max_piece_secs`, cutting at the quietest
/// 100ms window within `search_secs` before each limit so a cut lands in a pause, not a word.
pub(crate) fn quiet_cut_points(
    audio: &PcmAudio,
    max_piece_secs: f64,
    search_secs: f64,
) -> Vec<usize> {
    let sr = audio.sample_rate as usize;
    let max_piece = (max_piece_secs * sr as f64) as usize;
    let search = ((search_secs * sr as f64) as usize).min(max_piece / 2);
    let window = (sr / 10).max(1);
    let total = audio.samples.len();

    let mut cuts = Vec::new();
    let mut start = 0;
    while total - start > max_piece {
        let limit = start + max_piece;
        let mut best = (u64::MAX, limit);
        let mut w = limit - search;
        while w + window <= limit {
            let energy: u64 = audio.samples[w..w + window]
                .iter()
                .map(|&s| (s as i64 * s as i64) as u64)
                .sum();
            if energy < best.0 {
                best = (energy, w + window / 2);
            }
            w += window / 2;
        }
        cuts.push(best.1);
        start = best.1;
    }
    cuts
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tone_with_pauses(secs: usize, sr: u32, pauses_at: &[usize]) -> PcmAudio {
        let mut samples: Vec<i16> = (0..secs * sr as usize)
            .map(|i| ((i as f64 * 0.3).sin() * 8000.0) as i16)
            .collect();
        for &p in pauses_at {
            let from = p * sr as usize;
            samples[from..from + sr as usize / 2].fill(0);
        }
        PcmAudio {
            samples,
            sample_rate: sr,
        }
    }

    #[test]
    fn truncated_fmt_chunk_is_an_error_not_a_panic() {
        let path = std::env::temp_dir().join("vo-test-truncated-fmt.wav");
        let mut wav = b"RIFF\x00\x00\x00\x00WAVEfmt ".to_vec();
        wav.extend_from_slice(&16u32.to_le_bytes());
        wav.extend_from_slice(&[1, 0, 1, 0]); // declares 16 bytes, holds 4
        std::fs::write(&path, &wav).unwrap();
        assert!(read_pcm16_mono(&path).is_err());
        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn short_audio_is_not_split() {
        let audio = tone_with_pauses(120, 1000, &[]);
        assert!(quiet_cut_points(&audio, 290.0, 20.0).is_empty());
    }

    #[test]
    fn long_audio_is_cut_in_the_pause_before_each_limit() {
        // 410s like the real recording, with one pause just before the 290s limit
        let audio = tone_with_pauses(410, 1000, &[280]);
        let cuts = quiet_cut_points(&audio, 290.0, 20.0);
        assert_eq!(cuts.len(), 1);
        let cut_secs = cuts[0] as f64 / 1000.0;
        assert!(
            (280.0..280.5).contains(&cut_secs),
            "cut at {cut_secs}s, expected inside the pause at 280s"
        );
    }

    #[test]
    fn every_piece_respects_the_limit() {
        let audio = tone_with_pauses(1000, 1000, &[]);
        let cuts = quiet_cut_points(&audio, 290.0, 20.0);
        let mut bounds = vec![0];
        bounds.extend(&cuts);
        bounds.push(audio.samples.len());
        for pair in bounds.windows(2) {
            assert!(
                pair[1] - pair[0] <= 290_000,
                "piece of {} samples",
                pair[1] - pair[0]
            );
        }
    }

    #[test]
    fn wav_round_trip_preserves_samples() {
        let path = std::env::temp_dir().join("vo-test-wav-roundtrip.wav");
        let samples: Vec<i16> = (0..1600).map(|i| (i * 7 % 3000) as i16 - 1500).collect();
        write_pcm16_mono(&path, &samples, 16000).unwrap();
        let read = read_pcm16_mono(&path).unwrap();
        assert_eq!(read.sample_rate, 16000);
        assert_eq!(read.samples, samples);
        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn reads_wav_with_extra_list_chunk_like_ffmpeg_writes() {
        let path = std::env::temp_dir().join("vo-test-wav-list.wav");
        let mut bytes = b"RIFF\0\0\0\0WAVE".to_vec();
        bytes.extend_from_slice(b"fmt \x10\0\0\0\x01\0\x01\0\x80\x3e\0\0\0\x7d\0\0\x02\0\x10\0");
        bytes.extend_from_slice(b"LIST\x05\0\0\0INFOx\0");
        bytes.extend_from_slice(b"data\x04\0\0\0\x01\0\x02\0");
        std::fs::write(&path, bytes).unwrap();
        let read = read_pcm16_mono(&path).unwrap();
        assert_eq!(read.samples, vec![1, 2]);
        std::fs::remove_file(&path).ok();
    }
}

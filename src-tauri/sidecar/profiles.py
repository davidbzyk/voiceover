"""Voice profile management using JSON file storage.

Each profile is a directory under {data_dir}/profiles/{uuid}/ containing:
- profile.json: metadata (id, name, language, created_at)
- samples/{uuid}.wav: reference audio files
- samples/{uuid}.txt: transcript for each audio file
"""

import json
import logging
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("voiceover-tts.profiles")


def _validate_profile_id(profile_id: str) -> None:
    """Validate profile_id is safe for use as a path component."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', profile_id):
        raise ValueError(f"Invalid profile_id: {profile_id!r}")


def _profiles_dir(data_dir: Path) -> Path:
    d = data_dir / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_profiles(data_dir: Path) -> list[dict]:
    """List all voice profiles."""
    profiles = []
    pdir = _profiles_dir(data_dir)
    for profile_dir in sorted(pdir.iterdir()):
        meta_file = profile_dir / "profile.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                profiles.append(meta)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Skipping corrupt profile {profile_dir.name}: {e}")
    return profiles


def get_profile(data_dir: Path, profile_id: str) -> Optional[dict]:
    """Get a single profile by ID."""
    _validate_profile_id(profile_id)
    meta_file = _profiles_dir(data_dir) / profile_id / "profile.json"
    if not meta_file.exists():
        return None
    return json.loads(meta_file.read_text())


def create_profile(data_dir: Path, name: str, language: str = "en") -> dict:
    """Create a new voice profile."""
    profile_id = str(uuid.uuid4())
    profile_dir = _profiles_dir(data_dir) / profile_id
    profile_dir.mkdir(parents=True)
    (profile_dir / "samples").mkdir()

    meta = {
        "id": profile_id,
        "name": name,
        "language": language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (profile_dir / "profile.json").write_text(json.dumps(meta, indent=2))
    logger.info(f"Created profile: {name} ({profile_id})")
    return meta


def delete_profile(data_dir: Path, profile_id: str) -> bool:
    """Delete a voice profile and all its samples."""
    _validate_profile_id(profile_id)
    profile_dir = _profiles_dir(data_dir) / profile_id
    if not profile_dir.exists():
        return False
    shutil.rmtree(profile_dir)
    logger.info(f"Deleted profile: {profile_id}")
    return True


def add_sample(
    data_dir: Path,
    profile_id: str,
    audio_bytes: bytes,
    reference_text: str,
) -> dict:
    """Add a voice sample to a profile."""
    _validate_profile_id(profile_id)
    samples_dir = _profiles_dir(data_dir) / profile_id / "samples"
    if not samples_dir.exists():
        raise ValueError(f"Profile {profile_id} not found")

    sample_id = str(uuid.uuid4())
    wav_path = samples_dir / f"{sample_id}.wav"
    txt_path = samples_dir / f"{sample_id}.txt"

    wav_path.write_bytes(audio_bytes)
    txt_path.write_text(reference_text)

    logger.info(
        f"Added sample to {profile_id}: {sample_id} "
        f"({len(audio_bytes) // 1024}KB, {len(reference_text)} chars)"
    )
    return {"id": sample_id, "profile_id": profile_id}


def get_samples(data_dir: Path, profile_id: str) -> list[dict]:
    """List all samples for a profile."""
    _validate_profile_id(profile_id)
    samples_dir = _profiles_dir(data_dir) / profile_id / "samples"
    if not samples_dir.exists():
        return []

    samples = []
    for wav_file in sorted(samples_dir.glob("*.wav")):
        sample_id = wav_file.stem
        txt_file = samples_dir / f"{sample_id}.txt"
        samples.append({
            "id": sample_id,
            "audio_path": str(wav_file),
            "reference_text": txt_file.read_text() if txt_file.exists() else "",
        })
    return samples

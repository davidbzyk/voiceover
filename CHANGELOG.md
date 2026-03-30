# Changelog

All notable changes to VoiceOver will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Optional webcam overlay — circular picture-in-picture bubble during recording
- Webcam position toggle (bottom-left / bottom-right), persisted across sessions
- Canvas compositor burns webcam overlay into recorded video output
- `captureStream` feature detection with graceful fallback to screen-only recording

### Changed
- Compositor throttled to 30fps to match capture stream rate
- Recording chunks cleared after blob creation to reduce memory usage
- Webcam acquisition errors now surface to user instead of silent failure
- `read_file_bytes` IPC restricted to allowed directories
- Google Drive uploads no longer auto-set to public sharing
- `sync_to_static` config bridge disabled in production builds
- API key logging reduced to last 4 characters only

### Fixed
- Screen track `ended` event now triggers cleanup (prevents orphaned compositor loop)
- Canvas context null check prevents silent recording corruption
- Timer interval properly cleared on cancel/stop/component destroy
- Webcam position preference now persisted on toggle

### Security
- Removed `fs:scope-home-recursive` Tauri capability — narrowed to video and temp directories
- Added path validation to `read_file_bytes` IPC command
- Gated `read_static_config` and `sync_to_static` behind debug builds
- Added OAuth state parameter for CSRF protection
- Replaced `window.__voiceover_blob` globals with typed module-scoped store

### Config
- Added `preferences.webcam_enabled` (default: `false`)
- Added `preferences.webcam_position` (default: `"bottom-right"`, valid: `"bottom-left"` | `"bottom-right"`)
- Existing config files are automatically compatible — missing fields receive defaults

## [0.1.0] - 2026-03-22

### Added
- Initial release with screen recording, voice replacement, and Google Drive upload

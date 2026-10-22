---
id: standards/release-signing-notarization
schema: okf/schemas/v1/standard.json
type: Standard
title: Release build, signing and notarization
description: How a VoiceOver DMG is built headless, signed with the Developer ID, notarized and stapled.
domain: release
tags:
  - standard
  - release
  - macos
freshness: "2026-10-22T18:36:00Z"
version: 1.0.0
status: stable
standard_scope: release
conformance_level: mandatory
governance_body: principal
enforcement: manual-review
sources:
  - id: build-doc
    resource: docs/BUILD.md
    type: local_doc
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-22T18:36:00Z"
verified: []
relations:
  depends_on:
    - BUILD
  relates_to: []
  implements: []
  supersedes: []
  superseded_by: null
  part_of: standards
---

# Release build, signing and notarization

## Steps
1. Build headless: `CI=true pnpm tauri build`. Without `CI=true`, `bundle_dmg.sh` runs a Finder
   AppleScript that fails without a GUI session.
2. Signing is automatic from `signingIdentity: "Developer ID Application"` (team 8QFRX3LKFF) with the
   hardened runtime; the frozen sidecar is re-signed inside the bundle.
3. Notarize: `xcrun notarytool submit <dmg> --keychain-profile "notarytool-profile" --wait`.
4. Staple: `xcrun stapler staple <dmg>`, then check with `spctl`.

## Known failures
- Notary 403 "required agreement missing": the Apple developer agreement needs accepting in the
  developer account (2026-10-22).
- A stale `rw.*.dmg` or a still-mounted volume from a failed run blocks the next DMG build: remove
  the file and detach the volume.
- YouTube 403 in the frozen sidecar: the bundled yt-dlp is too old; bump its pin and rebuild.

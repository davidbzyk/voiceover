# VoiceOver — agent notes

## Knowledge bundle (`okf/`)
- `okf/` is this repo's Open Knowledge Format bundle: what we tried, why it broke, and the rules that came out of it.
- Read `okf/index.md` before changing voice engines, the sidecar, or the release flow.
- When a fix, failed attempt, or measured finding lands, add or update its note in the same PR (tombstone for anything abandoned, `lineage/evidence` for measurements, `standards` for rules), list it in its folder's `index.md`, and run `python3 <okf plugin>/scripts/okf_verify.py okf --docs-dir docs` until both tiers pass.

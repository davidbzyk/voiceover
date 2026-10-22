# VoiceOver — agent notes

## Knowledge bundle (`okf/`)
- `okf/` is this repo's Open Knowledge Format bundle: what we tried, why it broke, and the rules that came out of it.
- Read `okf/index.md` before changing voice engines, the sidecar, or the release flow.
- When a fix, failed attempt, or measured finding lands, add or update its note in the same PR (tombstone for anything abandoned, `lineage/evidence` for measurements, `standards` for rules), list it in its folder's `index.md`, and run the OKF verifier until both tiers pass: `/okf:verify` in Claude Code, or `python3 "$OKF_PLUGIN/scripts/okf_verify.py" okf --docs-dir docs` with `OKF_PLUGIN` set to a checkout of the `okf` plugin (the principal's is `~/Projects/PLUGINS/plugins/okf`).

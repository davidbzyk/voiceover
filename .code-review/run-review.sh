#!/usr/bin/env bash
# Review one pull request with the Codex review team and post the result. Called by action.yml;
# runs the same way on a laptop given the CR_* variables (CR_DRY_RUN=DIR posts nothing).
set -euo pipefail
repo=${GITHUB_WORKSPACE:-$PWD}
work=${RUNNER_TEMP:-$HOME/.cache/code-review-ci}/code-review
rm -rf "$work" && mkdir -p "$work"
# The agents may write anywhere in the checkout, .code-review/ included, so everything below runs
# from a copy taken before they start, outside the checkout.
here="$work/tool"
cp -R "$(cd "$(dirname "$0")" && pwd)" "$here"
export PYTHONPATH="$here/src"
# Agents can write inside the checkout, so Python never imports from the working directory:
# -P drops it from the path, and every Python step runs from this folder instead.
py=(python3 -P)

# The files this pull request changes, less the review tool itself.
# The change is measured from the merge base, as GitHub shows it: the target's tip may have moved.
base=$(git -C "$repo" merge-base "$CR_BASE" "$CR_HEAD")

# NUL-separated, so a name git would quote (non-ASCII, spaces) arrives as itself; deleted files
# count; --path=VALUE keeps a name that looks like an option a value.
changed=()
while IFS= read -r -d '' path; do
  case "$path" in .code-review/*|.code-review-out/*|"") ;; *) changed+=("$path") ;; esac
done < <(git -C "$repo" diff --no-ext-diff -z --name-only --diff-filter=ACMRD "$base" "$CR_HEAD")
# Files .gitattributes marks linguist-generated or linguist-vendored (snapshots, generated output)
# are skipped, as GitHub collapses them. The marks are read from the base, so a change cannot
# mark itself unreviewed. check-attr answers two attributes per path, in order.
# A git that cannot read them (check-attr --source needs 2.40) fails the run: skipping on an
# error would pass a change nobody reviewed.
paths=()
if [ ${#changed[@]} -gt 0 ]; then
  marks="$work/marks"
  if ! printf '%s\0' "${changed[@]}" | git -C "$repo" check-attr -z --stdin --source "$base" \
       linguist-generated linguist-vendored > "$marks"; then
    echo "code-review: git check-attr could not read the skip marks (git 2.40 or newer is needed)" >&2
    exit 2
  fi
  while IFS= read -r -d '' path && IFS= read -r -d '' _ && IFS= read -r -d '' generated \
        && IFS= read -r -d '' _ && IFS= read -r -d '' _ && IFS= read -r -d '' vendored; do
    case "$generated $vendored" in set\ *|true\ *|*\ set|*\ true) ;; *) paths+=("--path=$path") ;; esac
  done < "$marks"
fi
if [ ${#paths[@]} -eq 0 ]; then
  echo "code-review: no changed files outside .code-review/ and the generated or vendored ones, nothing to review"
  exit 0
fi

# One input picks the login: the ChatGPT subscription (a seeded auth.json) or an API key.
case "${CR_AUTH:-subscription}" in
  subscription)
    runner=codex-ci
    : "${CODEX_AUTH_JSON_B64:?auth is subscription: set the CODEX_AUTH_JSON_B64 secret}"
    export CODEX_HOME="$work/codex-home"
    mkdir -p "$CODEX_HOME"
    printf '%s' "$CODEX_AUTH_JSON_B64" | base64 -d > "$CODEX_HOME/auth.json"
    chmod 600 "$CODEX_HOME/auth.json"
    # Codex refreshes its login during the run; the poster checks against both versions.
    cp -p "$CODEX_HOME/auth.json" "$work/auth.seed.json"
    unset CODEX_AUTH_JSON_B64 OPENAI_API_KEY ;;
  api-key)
    runner=codex-ci-key
    : "${OPENAI_API_KEY:?auth is api-key: set the OPENAI_API_KEY secret}"
    unset CODEX_AUTH_JSON_B64 ;;
  *) echo "code-review: auth must be subscription or api-key, not ${CR_AUTH}" >&2; exit 2 ;;
esac

# Codex's sandbox lets agents write only inside the checkout, so the findings go there.
out="$repo/.code-review-out"
rm -rf "$out"

# CR_RUNNER and CR_REGISTRY swap in another runner row (a test's fake agent, a new provider).
runner=${CR_RUNNER:-$runner}
registry=()
if [ -n "${CR_REGISTRY:-}" ]; then registry=(--registry "$CR_REGISTRY"); fi

# The earlier threads, read with the token, for the reviewers (outside the checkout, so a PR cannot
# plant one). CR_PRIOR_REVIEW names a prepared file instead (tests); a dry run calls no GitHub API.
prior_file="$work/prior-review.md"
rm -f "$prior_file"
if [ -n "${CR_PRIOR_REVIEW:-}" ]; then
  cp "$CR_PRIOR_REVIEW" "$prior_file"
elif [ -z "${CR_DRY_RUN:-}" ]; then
  history=("${py[@]}" -m review_core.ci.history --repo "$CR_REPO" --pr "$CR_PR" --out "$prior_file"
           --repo-dir "$repo" --head "$CR_HEAD")
  if [ -n "${CR_BOT:-}" ]; then history+=(--bot "$CR_BOT"); fi
  (cd "$here" && "${history[@]}") || true
fi
prior=()
if [ -s "$prior_file" ]; then prior=(--prior-review "$prior_file"); fi

# The review never sees the GitHub token; only the post below gets it.
status=0
(cd "$here" && env -u GITHUB_TOKEN "${py[@]}" -m review_core.cli review --repo "$repo" --base "$base" \
  --head "$CR_HEAD" --runner "$runner" --model "${CR_MODEL:-gpt-6-luna}" \
  --effort "${CR_EFFORT:-high}" --out "$out" --runs "$work/runs" "${registry[@]}" \
  ${prior[@]+"${prior[@]}"} "${paths[@]}") || status=$?

# A failed run still has a review.json; post it so the pull request shows the failure.
# The agents could read the login; the poster refuses to post any of its values.
post=("${py[@]}" -m review_core.ci.github --runs "$work/runs" --repo-dir "$repo" --base "$base"
      --head "$CR_HEAD" --repo "$CR_REPO" --pr "$CR_PR" --summary "$out/pr-summary.md"
      --secret-env OPENAI_API_KEY)
if [ -n "${CODEX_HOME:-}" ]; then
  post+=(--secret-file "$CODEX_HOME/auth.json" --secret-file "$work/auth.seed.json")
fi
if [ -n "${CR_DRY_RUN:-}" ]; then post+=(--dry-run "$CR_DRY_RUN"); fi
if [ -n "${CR_TITLE:-}" ]; then post+=(--title "$CR_TITLE"); fi
if [ -n "${CR_BOT:-}" ]; then post+=(--bot "$CR_BOT"); fi
(cd "$here" && "${post[@]}")
exit "$status"

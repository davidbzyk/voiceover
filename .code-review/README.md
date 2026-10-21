# Custom Code Review

A team of seven Codex reviewers (security, tests, correctness, architecture, code quality,
compliance, language) and a validator review every pull request on a GitHub runner. The findings
are posted as one review, with inline comments on the lines they concern, plus a summary comment
that is updated on every push.

This folder is the tool itself, installed by `action/install.sh` from the code-review repository.
Do not edit it by hand; run the installer again to update it.

## Install

From a checkout of the code-review repository:

    sh action/install.sh /path/to/your/repo

This writes `.code-review/` and `.github/workflows/code-review.yml` into your repository. Commit
both, then choose how Codex signs in.

## Sign in with a ChatGPT subscription (the default)

Reviews run on your ChatGPT plan, with no per-token cost.

1. Sign in to Codex on your machine with your ChatGPT account: `codex login`.
2. Store that login as a repository secret. The file goes straight to GitHub and is not printed:

       base64 < ~/.codex/auth.json | gh secret set CODEX_AUTH_JSON_B64 -R OWNER/REPO

There is nothing else to set: the workflow uses the subscription unless told otherwise. If
reviews start failing to sign in later, the login has expired; run `codex login` again and repeat
step 2.

## Sign in with an OpenAI API key

Reviews are billed per token to the key, which makes their cost easy to track.

1. Store the key as a repository secret (`gh` asks for the value):

       gh secret set OPENAI_API_KEY -R OWNER/REPO

2. Tell the workflow to use it:

       gh variable set CODE_REVIEW_AUTH -b api-key -R OWNER/REPO

To go back to the subscription, delete the variable:

    gh variable delete CODE_REVIEW_AUTH -R OWNER/REPO

Both secrets can be set at once; `CODE_REVIEW_AUTH` decides which one a review uses.

## Options

Set these under `with:` in `.github/workflows/code-review.yml`.

| Input | Default | What it does |
|---|---|---|
| `model` | `gpt-6-luna` | The Codex model every reviewer runs on |
| `effort` | `high` | Reasoning effort |
| `title` | `Custom Code Review` | Heading of the review and the summary comment |
| `codex-version` | `0.161.0` | The Codex CLI version installed on the runner |
| `keep-run` | `false` | Upload the run folder as an artifact (see below) |
| `bot-login` | `github-actions[bot]` | The account reviews are posted as |

## Which pull requests are reviewed

Every non-draft pull request opened from a branch of this repository, on open, on each push and
when it is marked ready. Pull requests from forks and from Dependabot get no secrets on GitHub,
so they are skipped. The files under `.code-review/` are never reviewed.

Files that `.gitattributes` marks `linguist-generated` or `linguist-vendored` are skipped too, the
same files GitHub collapses in a pull request's diff. Mark snapshots, copied third-party code and
generated output there:

    research/** linguist-vendored
    dist/** linguist-generated

## Security

The reviewers read pull request text, which anyone opening a pull request can shape. The action
limits what a misled reviewer can do:

- It runs only for branches of this repository, so only people who can push here are reviewed.
- The tool runs from a copy outside the checkout, so reviewers cannot change the code that posts.
- The job token is not left in the checkout, and the review step never sees it.
- Before anything is posted, the text is checked against the Codex login, the API key and the
  GitHub token; on a match nothing is posted and the check fails.
- Your ChatGPT account's connected apps, computer use and browser use are switched off for the
  reviewers.
- The run folder, which holds every command the reviewers ran and its output, is uploaded only
  when `keep-run` is `true`. Anyone who can read the repository can download an artifact.

The reviewers can still read the Codex login on the runner, and their sandbox has network access.
Treat the subscription login or key as something a hostile pull request from a collaborator
could reach.

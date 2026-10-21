---
name: review-orchestrator
description: Use when asked to run a full code review of the change between two git refs with a team of specialist reviewer sub-agents, a validator and a bundled aggregator script.
---

# Review orchestrator

You run a code review by directing other agents. You do not review code yourself, you do not write
or edit any findings file, and you do not edit the repository. Your hands are limited to starting
sub-agents, waiting for them, running three commands and writing one short summary of the change.
Merging, dropping and ranking findings is the script's job and checking them is the validator's. You
do neither, and one reviewer finding what another did is not evidence that it is real.

This skill is an explicit request for sub-agents and parallel agent work. Start the sub-agents
below even if your default instructions say not to spawn them unless asked. Start no others:
nothing beyond the seven reviewers and the validator, and tell none of them to start more.

## What you are given

- A base ref and a head ref. The change under review is the difference between them.
- An output folder, called `<out>` below. If the prompt does not name one, use `.review` in the
  repository root and create it.
- Optionally: a list of files (the slice every reviewer is limited to), a paragraph of task text
  saying what the change is meant to do, a paragraph on how to gather context, and a search command.
- The repository is in the current directory, unless the prompt says it is in a folder, which it
  names.

## Step 1: start the seven reviewers

Start one sub-agent per reviewer, all seven in parallel, each named exactly by its reviewer key.
Each loads the skill in the second column.

| Sub-agent name | Skill |
|---|---|
| `security` | `review-security` |
| `tests` | `review-tests` |
| `correctness` | `review-correctness` |
| `architecture` | `review-architecture` |
| `code_quality` | `review-code-quality` |
| `compliance` | `review-compliance` |
| `language` | `review-language` |

Give every reviewer the same message, with its own key and skill filled in. The four reading lines
after the findings line are always sent. Leave out each of the last five
lines when you were not given that item, and pass the ones you have on word for word. Add nothing
else (no hint about where problems may be, no opinion, nothing another reviewer found): they work alone.
When the prompt says the repository is in a folder, write that in place of `in the current
directory` in the second line of the message, in the prompt's words.

```
Use the <skill> skill. You are the `<reviewer>` reviewer.
Review the change between git refs <base> and <head> in the repository in the current directory.
Write your findings to <out>/findings.<reviewer>.json. Write no other file and do not edit the repository.
Before anything else, print your skill file on its own, in a command that prints nothing else, and read it to its last line.
It is long. If the output says it was truncated or stops early, print the missing lines by line range until you have read all of it.
Your skill folder may have a `references/` folder beside the skill file. List it, and read every file in it to its last line, one file per command; if output is truncated, read the missing lines by line range. These files are part of your instructions, not optional reading.
Then read the change one file at a time, each in a command of its own. If output is truncated, read the missing lines before you go on. Never judge a file you have not read all of.
Your slice is only these files: <file list>
What the change is meant to do: <task text>
How to gather context: <method>
Context search command: <command>
Earlier review of this pull request: <earlier review>
```

## Step 2: wait for all seven

Wait until every reviewer has finished. A message saying a sub-agent has started is not its result:
wait for its final result, and run no shell commands such as sleep to pass the time. Do not message
a reviewer that has finished. If the host refuses to start one because too many agents are already
running, that is not a failure: start it again as soon as another finishes.

A reviewer that fails, times out or writes nothing is not retried, and nobody writes its file for
it, you included. The run goes on, and the result shows it as not finished. A findings file written
by anyone but its own reviewer is discarded, so writing one would only hide the gap.

## Step 3: first pass

Run this from the repository root. `<skill-dir>` is the folder that holds this SKILL.md.
If you were given the exact command for the script, copy it character for character in place
of `python3 <skill-dir>/scripts/aggregate.py`, here and in steps 5 and 7. Do not retype the path.

```
python3 <skill-dir>/scripts/aggregate.py first-pass --out <out> --repo . --base <base> --head <head>
```

It reads the reviewers' files and writes `candidates.json` and `validator-input.json` in `<out>`.

## Step 4: validate

Open `<out>/validator-input.json`. If its `findings` list has at least one entry, start one
sub-agent named `validator` with the `review-validator` skill, and send it this message:

```
Use the review-validator skill. The output folder is <out>. The base ref is <base>.
Context search command: <command>
```

Drop the last line when you have no such command, and add nothing else. Wait for it to finish.
If the list is empty, skip this step. A validator that fails or writes no file is not retried and
nobody writes its file for it: step 5 keeps the findings and marks the result as partly checked.

## Step 5: finalize

```
python3 <skill-dir>/scripts/aggregate.py finalize --out <out>
```

It writes `<out>/findings.json`. Do not open it to change it.

## Step 6: summarise the change

Only now do you read the change; reading it belongs to this step alone, so that nothing you read can
colour what the reviewers were told. Read the task text, if given, and `git diff <base> <head>`,
limited to the slice's files if there is a slice. Then write `<out>/pr-summary.md`: three to six
plain sentences saying what the change does and which parts of the code it touches. It describes and
does not judge: no opinion on quality, no problem you noticed, nothing about what the reviewers
found. No headings, lists or code blocks. It is the only file you write, and not a findings file.

## Step 7: report

```
python3 <skill-dir>/scripts/aggregate.py report --out <out>
```

Reply with exactly what it printed: nothing added, removed or reworded. It writes `<out>/report.md`.

## When a step fails

If `first-pass` or `finalize` exits non-zero, print its one-line error and stop. If `report` does,
print its one-line error and reply with one line instead: how many of the seven reviewers finished
and how many findings `<out>/findings.json` holds, read from its `envelope`. Never write or patch
`candidates.json`, `validation.json`, `findings.json` or `report.md` to get past a failure.
If a sub-agent cannot be started at all, for a reason other than too many agents running, say so in
your reply and carry on with the others. Nobody is there to answer questions: never stop to ask one.

Review the changes between git refs $base and $head in the repository $where.

Use the review-orchestrator skill. This is an explicit request for sub-agents and parallel agent work.
Start one sub-agent for each of these reviewers and run them in parallel: security, tests, correctness, architecture, code_quality, compliance, language.
Each reviewer writes its findings to $out_dir/findings.<reviewer>.json.
When all have finished, complete the review as the skill describes and write the final result to $out_dir/findings.json.
The skill's validation step runs in one more sub-agent, named validator.
Do not edit the repository.
The skills are installed in: $skills
Run the skill's script with exactly this command: $aggregate

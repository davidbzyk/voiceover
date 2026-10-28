import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Vitest runs from the repo root; import.meta.url is not a file URL under jsdom.
const text = readFileSync(resolve(process.cwd(), '.github/workflows/code-review.yml'), 'utf8');

/** A payload where a missing key reads as an empty string, like GitHub's contexts. */
function context(data: unknown): unknown {
	if (data === null || typeof data !== 'object') return data;
	return new Proxy(data as Record<string, unknown>, {
		get: (target, key) => context(target[key as string] ?? '')
	});
}

/** Evaluates the workflow's concurrency group for a github context; each `${{ }}` runs as JS. */
function concurrencyGroup(github: unknown): string {
	const group = text.match(/^ {2}group: (.+)$/m)![1];
	const format = (template: string, ...args: unknown[]) =>
		template.replace(/\{(\d+)\}/g, (_, i) => String(args[Number(i)]));
	return group.replace(/\$\{\{(.+?)\}\}/g, (_, expr) =>
		String(new Function('github', 'format', `return (${expr});`)(context(github), format))
	);
}

function group(action: string, changes?: object, runId = 1): string {
	const event: Record<string, unknown> = { action, pull_request: { number: 7 } };
	if (changes) event.changes = changes;
	return concurrencyGroup({ event, run_id: runId });
}

describe('code-review workflow', () => {
	it('gives a title or body edit its own group so it never cancels a running review', () => {
		const pushed = group('synchronize');
		expect(pushed).toBe('code-review-7');
		for (const changes of [{ title: { from: 'old' } }, { body: { from: 'old' } }]) {
			const edit = group('edited', changes, 11);
			expect(edit).toBe('code-review-7-edit-11');
			expect(edit).not.toBe(pushed);
			expect(edit).not.toBe(group('edited', changes, 12));
		}
	});

	it('lets a base change share the push group so it replaces the stale run', () => {
		expect(group('edited', { base: { ref: { from: 'main' } } }, 11)).toBe(group('synchronize'));
		for (const action of ['opened', 'reopened', 'ready_for_review']) {
			expect(group(action)).toBe('code-review-7');
		}
		expect(text).toContain('cancel-in-progress: true');
	});

	it('keeps the model and max effort', () => {
		expect(text).toContain("model: ${{ vars.CODE_REVIEW_MODEL || 'gpt-6-luna' }}");
		expect(text).toContain("effort: ${{ vars.CODE_REVIEW_EFFORT || 'max' }}");
	});
});

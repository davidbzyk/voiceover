import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import models from '$lib/fixtures/models-status.json';

vi.mock('$lib/tauri', () => ({ tauriInvoke: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

import { tauriInvoke } from '$lib/tauri';
import { localVoices } from '$lib/localVoice.svelte';
import Page from './+page.svelte';

let sidecarUp = false;

beforeEach(() => {
	vi.mocked(tauriInvoke).mockImplementation(async (cmd: string) => {
		if (cmd === 'test_local_connection') return sidecarUp;
		if (!sidecarUp) throw new Error('sidecar not running');
		if (cmd === 'list_local_voices') return [];
		if (cmd === 'check_model_status') return models;
		throw new Error(`unexpected command ${cmd}`);
	});
});

describe('Create Voice', () => {
	it('loads the engines when Retry Connection finds the sidecar it could not reach on open', async () => {
		render(Page);
		await fireEvent.click(await screen.findByText(/Retry Connection/));
		sidecarUp = true;
		await fireEvent.click(await screen.findByText(/Retry Connection/));
		await vi.waitFor(() => expect(localVoices.loaded).toBe(true));
		expect(localVoices.models.length).toBe(models.length);
	});
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import models from '$lib/fixtures/models-status.json';

/** The fixture with Whisper downloaded and no text-to-speech engine. */
const whisperOnly = models.map((m) => ({ ...m, downloaded: m.category === 'transcription' }));

/** Answers for the sidecar calls steps 2 and 3 make (profile, YouTube sample, transcript, saved sample). */
function sidecarFetch(args: { path: string }): string {
	if (args.path === '/profiles') return JSON.stringify({ id: 'p1', name: 'Me', language: 'en' });
	if (args.path === '/transcribe-path') return JSON.stringify({ text: 'Hello there.' });
	return '{}';
}

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

	it('can finish without a test when no text-to-speech engine is downloaded', async () => {
		sidecarUp = true;
		vi.mocked(tauriInvoke).mockImplementation(async (cmd: string, args?: unknown) => {
			if (cmd === 'test_local_connection') return true;
			if (cmd === 'list_local_voices') return [];
			if (cmd === 'check_model_status') return whisperOnly;
			if (cmd === 'extract_youtube_audio') return { audio_path: '/sample.wav', duration: 10 };
			if (cmd === 'sidecar_fetch') return sidecarFetch(args as { path: string });
			throw new Error(`unexpected command ${cmd}`);
		});
		render(Page);
		await fireEvent.input(await screen.findByPlaceholderText('My Voice'), { target: { value: 'Me' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Create' }));
		await fireEvent.input(await screen.findByPlaceholderText(/youtube\.com\/watch/), {
			target: { value: 'https://www.youtube.com/watch?v=abc' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Extract Audio' }));
		await fireEvent.click(await screen.findByRole('button', { name: /Save Sample/ }));
		await screen.findByText('Test Your Voice');

		await fireEvent.click(await screen.findByRole('button', { name: /Skip the test/ }));
		expect(await screen.findByText('Your voice is ready!')).toBeTruthy();
	});
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import models from './fixtures/models-status.json';

vi.mock('./tauri', () => ({ tauriInvoke: vi.fn() }));

import { tauriInvoke } from './tauri';
import { appState } from './state.svelte';
import StatusBar from './StatusBar.svelte';

const profiles = [{ id: '4ad88b19', name: 'Michael Jackson', language: 'en' }];

beforeEach(() => {
	vi.mocked(tauriInvoke).mockImplementation(async (cmd: string) => {
		if (cmd === 'get_sidecar_status') return { running: true, healthy: true };
		if (cmd === 'list_local_voices') return profiles;
		if (cmd === 'check_model_status') return models;
		throw new Error(`unexpected command ${cmd}`);
	});
});

describe('StatusBar', () => {
	it('names the local voice and engine once the config loads after the bar mounted', async () => {
		vi.stubGlobal('__TAURI_INTERNALS__', {});
		render(StatusBar);
		// The bar mounts with the default config, then loadConfig replaces it (what the app does at startup).
		appState.config = {
			...appState.config,
			provider: 'local',
			local_voice_profile_id: '4ad88b19',
			local_engine: 'qwen-tts-1.7B'
		};
		expect(await screen.findByText('Michael Jackson · Qwen3-TTS 1.7B')).toBeTruthy();

		appState.config.local_engine = 'cosyvoice3-0.5B';
		await tick();
		expect(screen.getByText('Michael Jackson · CosyVoice3 0.5B')).toBeTruthy();
		vi.unstubAllGlobals();
	});
});

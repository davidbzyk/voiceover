import { describe, it, expect } from 'vitest';
import models from './fixtures/models-status.json';
import { describeChoice, engineOptions, settingsChoice } from './localVoice.svelte';
import type { VoiceboxModelStatus } from './voicebox';

const recorded = models as VoiceboxModelStatus[];
const voices = [{ id: 'el-2', name: 'Adam', description: '', is_default: true }];
const profiles = [{ id: '4ad88b19', name: 'Michael Jackson' }];

describe('engineOptions', () => {
	it('lists speech-to-speech first, then every text-to-speech engine, from the sidecar rows', () => {
		const options = engineOptions(recorded);
		expect(options.map((o) => o.key)).toEqual([
			'cosyvoice3-0.5B',
			'qwen-tts-1.7B',
			'voxcpm2',
			'moss-tts-local-v1.5',
			'omnivoice',
			'fish-s2-pro',
			'chatterbox'
		]);
		expect(options[0]).toEqual({
			key: 'cosyvoice3-0.5B',
			name: 'CosyVoice3 0.5B',
			kind: 'speech-to-speech',
			downloaded: true
		});
		expect(options.slice(1).every((o) => o.kind === 'text-to-speech')).toBe(true);
	});

	it('keeps an engine that is not downloaded, marked so the picker can grey it', () => {
		const withoutVox = recorded.map((m) => (m.model_name === 'voxcpm2' ? { ...m, downloaded: false } : m));
		expect(engineOptions(withoutVox).find((o) => o.key === 'voxcpm2')?.downloaded).toBe(false);
	});

	it('offers only engines that read text when asked', () => {
		expect(engineOptions(recorded, true).map((o) => o.kind)).not.toContain('speech-to-speech');
	});
});

describe('describeChoice', () => {
	const engines = engineOptions(recorded);

	it('names a local voice and its engine', () => {
		const choice = { provider: 'local' as const, voiceId: '4ad88b19', engine: 'qwen-tts-1.7B' };
		expect(describeChoice(choice, { voices }, profiles, engines)).toBe('Michael Jackson · Qwen3-TTS 1.7B');
	});

	it('says when a local voice has no engine yet', () => {
		const choice = { provider: 'local' as const, voiceId: '4ad88b19', engine: '' };
		expect(describeChoice(choice, { voices }, profiles, engines)).toBe('Michael Jackson · No engine');
	});

	it('names an ElevenLabs voice', () => {
		expect(describeChoice({ provider: 'elevenlabs', voiceId: 'el-2' }, { voices }, profiles, engines)).toBe(
			'Adam · ElevenLabs'
		);
	});
});

describe('settingsChoice', () => {
	it('is the saved profile and engine for local', () => {
		expect(
			settingsChoice({ provider: 'local', voices, local_voice_profile_id: 'p1', local_engine: 'voxcpm2' })
		).toEqual({ provider: 'local', voiceId: 'p1', engine: 'voxcpm2' });
	});

	it('is the default ElevenLabs voice otherwise', () => {
		expect(settingsChoice({ provider: 'elevenlabs', voices, local_voice_profile_id: '', local_engine: '' })).toEqual({
			provider: 'elevenlabs',
			voiceId: 'el-2'
		});
	});
});

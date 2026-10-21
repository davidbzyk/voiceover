import { describe, it, expect } from 'vitest';
import { buildVoiceOptions, choiceKey, defaultVoiceChoice, parseChoiceKey } from './conversion';

const voices = [
	{ id: 'el-1', name: 'Rachel', description: '', is_default: false },
	{ id: 'el-2', name: 'Adam', description: '', is_default: true }
];

describe('buildVoiceOptions', () => {
	it('lists ElevenLabs voices and local profiles together', () => {
		const options = buildVoiceOptions({ voices, elevenlabs_api_key: 'k' }, [{ id: 'p1', name: 'DJT' }]);
		expect(options).toEqual([
			{ provider: 'elevenlabs', voiceId: 'el-1', name: 'Rachel' },
			{ provider: 'elevenlabs', voiceId: 'el-2', name: 'Adam' },
			{ provider: 'local', voiceId: 'p1', name: 'DJT' }
		]);
	});

	it('leaves out ElevenLabs voices when no API key is set', () => {
		const options = buildVoiceOptions({ voices, elevenlabs_api_key: '' }, [{ id: 'p1', name: 'DJT' }]);
		expect(options.map((o) => o.provider)).toEqual(['local']);
	});
});

describe('defaultVoiceChoice', () => {
	it('uses the local profile when the provider is local', () => {
		expect(defaultVoiceChoice({ provider: 'local', voices, local_voice_profile_id: 'p1' })).toEqual({
			provider: 'local',
			voiceId: 'p1'
		});
	});

	it('uses the default ElevenLabs voice otherwise', () => {
		expect(defaultVoiceChoice({ provider: 'elevenlabs', voices, local_voice_profile_id: '' })).toEqual({
			provider: 'elevenlabs',
			voiceId: 'el-2'
		});
	});

	it('is null when nothing is configured', () => {
		expect(defaultVoiceChoice({ provider: 'local', voices: [], local_voice_profile_id: '' })).toBeNull();
	});
});

describe('choiceKey', () => {
	it('round-trips ids that contain colons', () => {
		const choice = { provider: 'local' as const, voiceId: 'a:b-c' };
		expect(parseChoiceKey(choiceKey(choice))).toEqual(choice);
	});
});

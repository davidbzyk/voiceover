import { describe, it, expect } from 'vitest';
import { getRequiredModelNames } from './models';

describe('getRequiredModelNames', () => {
	it('voice replacement needs CosyVoice speech-to-speech, never Qwen text-to-speech', () => {
		const required = getRequiredModelNames({ whisper_model: 'whisper-large-v3-turbo' });
		expect(required).toContain('cosyvoice3-0.5B');
		expect(required).not.toContain('qwen-tts-1.7B');
	});

	it('creating a voice needs Qwen for the test sentence', () => {
		const required = getRequiredModelNames({ whisper_model: 'whisper-medium' }, 'create-voice');
		expect(required).toEqual(['whisper-medium', 'qwen-tts-1.7B']);
	});
});

import { describe, it, expect } from 'vitest';
import { getRequiredModelNames } from './models';

describe('getRequiredModelNames', () => {
	it('needs only Whisper until an engine is picked', () => {
		expect(getRequiredModelNames({ whisper_model: 'whisper-large-v3-turbo' })).toEqual(['whisper-large-v3-turbo']);
		expect(getRequiredModelNames({ whisper_model: 'whisper-large-v3-turbo' }, null)).toEqual([
			'whisper-large-v3-turbo'
		]);
	});

	it('needs the picked engine as well, whichever it is', () => {
		expect(getRequiredModelNames({ whisper_model: 'whisper-medium' }, 'voxcpm2')).toEqual([
			'whisper-medium',
			'voxcpm2'
		]);
	});
});

import { describe, it, expect, vi } from 'vitest';
import {
	buildVoiceOptions,
	choiceKey,
	defaultVoiceChoice,
	parseChoiceKey,
	releaseObjectUrl,
	runConversion,
	type VoiceChoice,
	shouldLoadLocalVoices
} from './conversion';
import { activeConversion, runExclusive } from './activeConversion.svelte';

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

describe('shouldLoadLocalVoices', () => {
	it('skips the local engine for ElevenLabs-only setups', () => {
		expect(shouldLoadLocalVoices({ provider: 'elevenlabs', local_voice_profile_id: '' })).toBe(false);
	});

	it('loads local voices when local is the provider or a local profile is set', () => {
		expect(shouldLoadLocalVoices({ provider: 'local', local_voice_profile_id: '' })).toBe(true);
		expect(shouldLoadLocalVoices({ provider: 'elevenlabs', local_voice_profile_id: 'p1' })).toBe(true);
	});
});

describe('runExclusive', () => {
	it('marks the owner while its conversion runs and clears it after', async () => {
		let during: string | null = null;
		await runExclusive('card-a', async () => {
			during = activeConversion.owner;
		});
		expect(during).toBe('card-a');
		expect(activeConversion.owner).toBeNull();
	});

	it('clears the owner when the conversion fails', async () => {
		await expect(runExclusive('card-a', () => Promise.reject(new Error('boom')))).rejects.toThrow('boom');
		expect(activeConversion.owner).toBeNull();
	});

	it('does not start a second conversion while another owner is running', async () => {
		let release!: () => void;
		const first = runExclusive('card-a', () => new Promise<void>((r) => (release = r)));
		await expect(runExclusive('card-b', async () => 'ran')).rejects.toThrow(/another conversion/i);
		release();
		await first;
	});
});

describe('runExclusive for the same owner', () => {
	it('refuses a second run while the same owner is still converting (a remounted card)', async () => {
		let finish!: () => void;
		const first = runExclusive('/r/a.mp4', () => new Promise<void>((r) => (finish = r)));
		await expect(runExclusive('/r/a.mp4', async () => 'second')).rejects.toThrow(/another conversion/i);
		finish();
		await first;
		expect(activeConversion.owner).toBeNull();
	});
});

describe('releaseObjectUrl', () => {
	it('revokes a page-owned blob URL', () => {
		const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
		releaseObjectUrl('blob:page-video', 'blob:recording');
		expect(revoke).toHaveBeenCalledWith('blob:page-video');
		revoke.mockRestore();
	});
	it('leaves the shared recording blob and non-blob URLs alone', () => {
		const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
		releaseObjectUrl('blob:recording', 'blob:recording');
		releaseObjectUrl('/Users/me/rec.webm', 'blob:recording');
		releaseObjectUrl('', null);
		expect(revoke).not.toHaveBeenCalled();
		revoke.mockRestore();
	});
});

describe('runExclusive cancellable flag', () => {
	it('records whether the running conversion can be cancelled, for a page that remounts mid-run', async () => {
		let seen: boolean | undefined;
		await runExclusive('preview', async () => {
			seen = activeConversion.cancellable;
		}, false);
		expect(seen).toBe(false);
		await runExclusive('/r/b.mp4', async () => {
			seen = activeConversion.cancellable;
		});
		expect(seen).toBe(true);
		expect(activeConversion.owner).toBeNull();
	});
});

// Compile-time only (checked by `pnpm check`): each command accepts only its own arguments.
export function _conversionArgsAreTyped(choice: VoiceChoice | null) {
	// @ts-expect-error process_recording has no `path`
	void runConversion('process_recording', { path: '/a.mp4', voiceChoice: choice }, () => {});
	// @ts-expect-error reconvert_recording has no `recordingPath`
	void runConversion('reconvert_recording', { recordingPath: '/a.webm', voiceChoice: choice }, () => {});
}

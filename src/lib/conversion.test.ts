import { describe, it, expect, vi } from 'vitest';
import {
	buildVoiceOptions,
	choiceKey,
	defaultVoiceChoice,
	parseChoiceKey,
	choiceReady,
	pickVoice,
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
	it('uses the local profile and saved engine when the provider is local', () => {
		expect(
			defaultVoiceChoice({ provider: 'local', voices, local_voice_profile_id: 'p1', local_engine: 'voxcpm2' })
		).toEqual({ provider: 'local', voiceId: 'p1', engine: 'voxcpm2' });
	});

	it('leaves the engine unpicked when none is saved', () => {
		expect(
			defaultVoiceChoice({ provider: 'local', voices, local_voice_profile_id: 'p1', local_engine: '' })
		).toEqual({ provider: 'local', voiceId: 'p1', engine: null });
	});

	it('uses the default ElevenLabs voice otherwise', () => {
		expect(
			defaultVoiceChoice({ provider: 'elevenlabs', voices, local_voice_profile_id: '', local_engine: 'voxcpm2' })
		).toEqual({ provider: 'elevenlabs', voiceId: 'el-2' });
	});

	it('is null when nothing is configured', () => {
		expect(
			defaultVoiceChoice({ provider: 'local', voices: [], local_voice_profile_id: '', local_engine: '' })
		).toBeNull();
	});
});

describe('choiceReady', () => {
	it('needs an engine for a local voice, and nothing more for ElevenLabs', () => {
		expect(choiceReady({ provider: 'local', voiceId: 'p1', engine: null })).toBe(false);
		expect(choiceReady({ provider: 'local', voiceId: 'p1', engine: 'voxcpm2' })).toBe(true);
		expect(choiceReady({ provider: 'elevenlabs', voiceId: 'el-1' })).toBe(true);
		expect(choiceReady(null)).toBe(false);
	});
});

describe('pickVoice', () => {
	it('keeps the engine already picked when switching between local voices', () => {
		const current = { provider: 'local' as const, voiceId: 'p1', engine: 'fish-s2-pro' };
		expect(pickVoice('local:p2', current, { local_engine: 'voxcpm2' })).toEqual({
			provider: 'local',
			voiceId: 'p2',
			engine: 'fish-s2-pro'
		});
	});

	it('takes the saved engine when coming from ElevenLabs', () => {
		const current = { provider: 'elevenlabs' as const, voiceId: 'el-2' };
		expect(pickVoice('local:p2', current, { local_engine: 'voxcpm2' }).engine).toBe('voxcpm2');
	});

	it('drops the engine for an ElevenLabs voice', () => {
		const current = { provider: 'local' as const, voiceId: 'p1', engine: 'fish-s2-pro' };
		expect(pickVoice('elevenlabs:el-1', current, { local_engine: '' })).toEqual({
			provider: 'elevenlabs',
			voiceId: 'el-1'
		});
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

describe('runExclusive shared progress and failure', () => {
	it('keeps progress and the failure in shared state, so a remounted card can show them', async () => {
		let during = '';
		await runExclusive('/r/c.mp4', async (report) => {
			report('Converting voice 40%');
			during = activeConversion.progress;
		});
		expect(during).toBe('Converting voice 40%');
		expect(activeConversion.progress).toBe('');

		await expect(
			runExclusive('/r/c.mp4', async () => {
				throw new Error('ffmpeg failed');
			})
		).rejects.toThrow('ffmpeg failed');
		expect(activeConversion.failure).toEqual({ owner: '/r/c.mp4', message: 'ffmpeg failed' });

		await runExclusive('/r/d.mp4', async () => {});
		expect(activeConversion.failure).toBeNull();
	});
});

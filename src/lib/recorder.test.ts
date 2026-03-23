import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
	generateSessionId,
	selectVideoMimeType,
	getAudioDevices,
	pauseRecording,
	cancelRecording
} from './recorder.svelte';

describe('generateSessionId', () => {
	it('starts with "rec-" prefix', () => {
		const id = generateSessionId();
		expect(id.startsWith('rec-')).toBe(true);
	});

	it('contains timestamp component between first and second hyphen', () => {
		const id = generateSessionId();
		const parts = id.split('-');
		// parts[0] = "rec", parts[1] = timestamp (Date.now()), parts[2] = random
		const timestamp = Number(parts[1]);
		expect(timestamp).toBeGreaterThan(0);
		// Timestamp should be a recent Date.now() value
		expect(timestamp).toBeLessThanOrEqual(Date.now());
		expect(timestamp).toBeGreaterThan(Date.now() - 10000);
	});

	it('contains random suffix', () => {
		const id = generateSessionId();
		const parts = id.split('-');
		// The random suffix is the last part
		const suffix = parts[2];
		expect(suffix.length).toBeGreaterThan(0);
		// Should be alphanumeric (base-36)
		expect(suffix).toMatch(/^[a-z0-9]+$/);
	});

	it('generates 100 unique IDs', () => {
		const ids = new Set<string>();
		for (let i = 0; i < 100; i++) {
			ids.add(generateSessionId());
		}
		expect(ids.size).toBe(100);
	});
});

describe('selectVideoMimeType', () => {
	const originalMediaRecorder = globalThis.MediaRecorder;

	afterEach(() => {
		if (originalMediaRecorder) {
			globalThis.MediaRecorder = originalMediaRecorder;
		} else {
			delete (globalThis as any).MediaRecorder;
		}
	});

	it('prefers vp8,opus when supported', () => {
		(globalThis as any).MediaRecorder = {
			isTypeSupported: (type: string) => true
		};
		expect(selectVideoMimeType()).toBe('video/webm;codecs=vp8,opus');
	});

	it('falls back to video/webm when vp8 unsupported', () => {
		(globalThis as any).MediaRecorder = {
			isTypeSupported: (type: string) => type === 'video/webm'
		};
		expect(selectVideoMimeType()).toBe('video/webm');
	});

	it('returns empty when no webm support', () => {
		(globalThis as any).MediaRecorder = {
			isTypeSupported: () => false
		};
		expect(selectVideoMimeType()).toBe('');
	});
});

describe('getAudioDevices', () => {
	it('filters to only audioinput devices', async () => {
		const mockDevices = [
			{ kind: 'audioinput', deviceId: 'mic1', label: 'Mic 1' },
			{ kind: 'videoinput', deviceId: 'cam1', label: 'Camera 1' },
			{ kind: 'audiooutput', deviceId: 'spk1', label: 'Speaker 1' },
			{ kind: 'audioinput', deviceId: 'mic2', label: 'Mic 2' }
		];

		vi.stubGlobal('navigator', {
			mediaDevices: {
				enumerateDevices: vi.fn().mockResolvedValue(mockDevices)
			}
		});

		const devices = await getAudioDevices();
		expect(devices).toHaveLength(2);
		expect(devices.every((d) => d.kind === 'audioinput')).toBe(true);
		expect(devices[0].deviceId).toBe('mic1');
		expect(devices[1].deviceId).toBe('mic2');

		vi.unstubAllGlobals();
	});
});

describe('guard functions', () => {
	it('pauseRecording does not throw with no active recorder', () => {
		expect(() => pauseRecording()).not.toThrow();
	});

	it('cancelRecording does not throw with no active recording', () => {
		expect(() => cancelRecording()).not.toThrow();
	});
});

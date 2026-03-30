import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { isTauri, appState } from './state.svelte';
import type { AppConfig, Voice } from './state.svelte';

describe('isTauri', () => {
	afterEach(() => {
		delete (window as any).__TAURI_INTERNALS__;
	});

	it('returns false when __TAURI_INTERNALS__ not set', () => {
		delete (window as any).__TAURI_INTERNALS__;
		expect(isTauri()).toBe(false);
	});

	it('returns true when __TAURI_INTERNALS__ is set', () => {
		(window as any).__TAURI_INTERNALS__ = {};
		expect(isTauri()).toBe(true);
	});
});

describe('AppState defaults', () => {
	it('starts in ready recording state', () => {
		expect(appState.recordingState).toBe('ready');
	});

	it('has empty API key', () => {
		expect(appState.config.elevenlabs_api_key).toBe('');
	});

	it('has voice replacement enabled', () => {
		expect(appState.config.preferences.voice_replacement_enabled).toBe(true);
	});

	it('has webcam disabled', () => {
		expect(appState.config.preferences.webcam_enabled).toBe(false);
	});

	it('has fullscreen default capture mode', () => {
		expect(appState.config.preferences.default_capture_mode).toBe('fullscreen');
	});

	it('has Google Drive disconnected', () => {
		expect(appState.config.google_drive.connected).toBe(false);
	});
});

describe('derived: selectedVoice', () => {
	beforeEach(() => {
		appState.config.voices = [];
	});

	afterEach(() => {
		appState.config.voices = [];
	});

	it('returns null with no voices', () => {
		expect(appState.selectedVoice).toBeNull();
	});

	it('returns default voice when one is_default=true', () => {
		const voices: Voice[] = [
			{ id: 'v1', name: 'Voice One', description: 'First', is_default: false },
			{ id: 'v2', name: 'Voice Two', description: 'Second', is_default: true },
			{ id: 'v3', name: 'Voice Three', description: 'Third', is_default: false }
		];
		appState.config.voices = voices;
		expect(appState.selectedVoice).toEqual(voices[1]);
	});

	it('falls back to first voice when none is default', () => {
		const voices: Voice[] = [
			{ id: 'v1', name: 'Voice One', description: 'First', is_default: false },
			{ id: 'v2', name: 'Voice Two', description: 'Second', is_default: false }
		];
		appState.config.voices = voices;
		expect(appState.selectedVoice).toEqual(voices[0]);
	});
});

describe('derived: isConfigured', () => {
	afterEach(() => {
		appState.config.elevenlabs_api_key = '';
		appState.config.voices = [];
	});

	it('returns false when API key empty even with voices', () => {
		appState.config.elevenlabs_api_key = '';
		appState.config.voices = [
			{ id: 'v1', name: 'Voice', description: 'Desc', is_default: true }
		];
		expect(appState.isConfigured).toBe(false);
	});

	it('returns false when no voices even with API key', () => {
		appState.config.elevenlabs_api_key = 'sk-test-key';
		appState.config.voices = [];
		expect(appState.isConfigured).toBe(false);
	});

	it('returns true when both API key and voices exist', () => {
		appState.config.elevenlabs_api_key = 'sk-test-key';
		appState.config.voices = [
			{ id: 'v1', name: 'Voice', description: 'Desc', is_default: true }
		];
		expect(appState.isConfigured).toBe(true);
	});
});

describe('reset()', () => {
	it('resets all recording state fields to defaults', () => {
		// Set non-default values
		appState.recordingState = 'recording';
		appState.recordingPath = '/some/path';
		appState.outputPath = '/output/path';
		appState.processingProgress = 75;
		appState.processingStage = 'encoding';
		appState.errorMessage = 'something failed';
		appState.recordingDuration = 120;

		appState.reset();

		expect(appState.recordingState).toBe('ready');
		expect(appState.recordingPath).toBe('');
		expect(appState.outputPath).toBe('');
		expect(appState.processingProgress).toBe(0);
		expect(appState.processingStage).toBe('');
		expect(appState.errorMessage).toBe('');
		expect(appState.recordingDuration).toBe(0);
	});

	it('resets webcamStream to null', () => {
		// Create a minimal mock MediaStream
		const mockTrack = { stop: vi.fn(), kind: 'video', id: '1', label: '', enabled: true, muted: false, readyState: 'live' as const, contentHint: '', onended: null, onmute: null, onunmute: null, clone: vi.fn(), getCapabilities: vi.fn(), getConstraints: vi.fn(), getSettings: vi.fn(), applyConstraints: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() };
		const mockStream = { getTracks: () => [mockTrack], getVideoTracks: () => [mockTrack], getAudioTracks: () => [], id: 'test', active: true, onaddtrack: null, onremovetrack: null, addTrack: vi.fn(), removeTrack: vi.fn(), clone: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() } as unknown as MediaStream;
		appState.webcamStream = mockStream;
		appState.reset();
		expect(appState.webcamStream).toBeNull();
	});

	it('stops webcam tracks on reset', () => {
		const stopFn = vi.fn();
		const mockTrack = { stop: stopFn, kind: 'video' };
		const mockStream = { getTracks: () => [mockTrack] } as unknown as MediaStream;
		appState.webcamStream = mockStream;
		appState.reset();
		expect(stopFn).toHaveBeenCalled();
	});
});

describe('loadConfig fallback', () => {
	let store: Record<string, string>;

	beforeEach(() => {
		vi.restoreAllMocks();
		delete (window as any).__TAURI_INTERNALS__;
		store = {};
		vi.stubGlobal('localStorage', {
			getItem: vi.fn((key: string) => store[key] ?? null),
			setItem: vi.fn((key: string, val: string) => { store[key] = val; }),
			removeItem: vi.fn((key: string) => { delete store[key]; })
		});
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		// Reset config to defaults
		appState.config.elevenlabs_api_key = '';
		appState.config.voices = [];
	});

	it('loads from localStorage when not in Tauri and no static config', async () => {
		// Mock fetch to fail (no static config file)
		vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network error'));

		// Pre-populate localStorage
		const storedConfig: Partial<AppConfig> = {
			elevenlabs_api_key: 'sk-from-localstorage',
			voices: [{ id: 'v1', name: 'Stored Voice', description: 'From LS', is_default: true }]
		};
		store['voiceover-config'] = JSON.stringify(storedConfig);

		await appState.loadConfig();

		expect(appState.config.elevenlabs_api_key).toBe('sk-from-localstorage');
		expect(appState.config.voices[0].name).toBe('Stored Voice');
	});

	it('uses defaults when nothing available', async () => {
		vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network error'));

		// Reset to defaults first
		appState.config.elevenlabs_api_key = '';
		appState.config.voices = [];

		await appState.loadConfig();

		expect(appState.config.elevenlabs_api_key).toBe('');
		expect(appState.config.voices).toEqual([]);
	});
});

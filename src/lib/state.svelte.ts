import { logger } from './logger';
import { tauriInvoke } from './tauri';

const STORAGE_KEY = 'voiceover-config';

/** Strip secrets before persisting to localStorage — secrets are stored in Tauri app data only */
function sanitizeForStorage(config: AppConfig): Partial<AppConfig> {
	return {
		...config,
		elevenlabs_api_key: '',
		google_drive: {
			...config.google_drive,
			client_secret: '',
			access_token: '',
			refresh_token: '',
		},
	};
}

declare global {
	interface Window {
		__TAURI_INTERNALS__?: Record<string, unknown>;
	}
}

export function isTauri(): boolean {
	return typeof window !== 'undefined' && !!window.__TAURI_INTERNALS__;
}

export type Voice = {
	id: string;
	name: string;
	description: string;
	is_default: boolean;
};

export type GoogleDrive = {
	client_id: string;
	client_secret: string;
	access_token: string;
	refresh_token: string;
	email: string;
	connected: boolean;
	expires_at: number;
};

export type AppConfig = {
	elevenlabs_api_key: string;
	voices: Voice[];
	output_dir: string;
	preferences: {
		default_capture_mode: string;
		webcam_enabled: boolean;
		voice_replacement_enabled: boolean;
		webcam_position: 'bottom-left' | 'bottom-right';
	};
	google_drive: GoogleDrive;
};

export type RecordingState =
	| 'ready'
	| 'selecting'
	| 'selecting-region'
	| 'recording'
	| 'paused'
	| 'recorded'
	| 'processing'
	| 'complete'
	| 'saved';

class AppState {
	config = $state<AppConfig>({
		elevenlabs_api_key: '',
		voices: [],
		output_dir: '',
		preferences: {
			default_capture_mode: 'fullscreen',
			webcam_enabled: false,
			voice_replacement_enabled: true,
			webcam_position: 'bottom-right'
		},
		google_drive: {
			client_id: '',
			client_secret: '',
			access_token: '',
			refresh_token: '',
			email: '',
			connected: false,
			expires_at: 0
		}
	});

	webcamStream = $state<MediaStream | null>(null);
	webcamVideoEl = $state<HTMLVideoElement | null>(null);
	regionScreenshot = $state<string>('');
	recordingState = $state<RecordingState>('ready');
	recordingPath = $state('');
	outputPath = $state('');
	processingProgress = $state(0);
	processingStage = $state('');
	errorMessage = $state('');
	recordingDuration = $state(0);

	ffmpegAvailable = $state(true);

	selectedVoice = $derived(
		this.config.voices.find((v) => v.is_default) ?? this.config.voices[0] ?? null
	);

	isConfigured = $derived(
		this.config.elevenlabs_api_key.length > 0 && this.config.voices.length > 0
	);

	/**
	 * Config loading priority:
	 * 1. Tauri app data (native desktop) — canonical source
	 * 2. static/_config.json (browser bridge) — dev-mode fallback, seeds back to Tauri
	 * 3. localStorage (browser fallback) — last resort
	 */
	async loadConfig() {
		if (isTauri()) {
			try {
				const tauriConfig = await tauriInvoke<AppConfig>('get_config');
				if (tauriConfig.elevenlabs_api_key) {
					this.config = tauriConfig;
					localStorage.setItem(STORAGE_KEY, JSON.stringify(sanitizeForStorage(this.config)));
					logger.configLoaded('Tauri app data');
					return;
				}
				logger.warn('config', 'Tauri config has no API key, checking static fallback');
			} catch (e) {
				logger.error('config', 'Failed to load from Tauri', e);
			}
		}

		// Browser mode (or Tauri fallback): try fetching the synced config file
		try {
			const resp = await fetch('/_config.json');
			if (resp.ok) {
				const data = await resp.json();
				if (data.elevenlabs_api_key) {
					this.config = { ...this.config, ...data };
					localStorage.setItem(STORAGE_KEY, JSON.stringify(sanitizeForStorage(this.config)));
					logger.configLoaded('static/_config.json');
					// If in Tauri, persist to app data so it's picked up next time
					if (isTauri()) {
						try {
							await tauriInvoke('save_config', { config: this.config });
							logger.configSaved('Tauri app data (seeded from static)');
						} catch {
							// Non-fatal — config is loaded, just not persisted to Tauri
						}
					}
					return;
				}
			}
		} catch {
			// File doesn't exist yet — fall through to localStorage
		}

		// Final fallback: localStorage
		try {
			const stored = localStorage.getItem(STORAGE_KEY);
			if (stored) {
				this.config = { ...this.config, ...JSON.parse(stored) };
				logger.configLoaded('localStorage');
			} else {
				logger.warn('config', 'No config found — using defaults');
			}
		} catch (e) {
			logger.error('config', 'Failed to load from localStorage', e);
		}
	}

	async saveConfig() {
		// Always save to localStorage (shared between Tauri webview & browser)
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(sanitizeForStorage(this.config)));
			logger.configSaved('localStorage');
		} catch (e) {
			logger.error('config', 'Failed to save to localStorage', e);
		}
		// Also save to Tauri app data if available
		if (isTauri()) {
			try {
				await tauriInvoke('save_config', { config: this.config });
				logger.configSaved('Tauri app data');
			} catch (e) {
				logger.error('config', 'Failed to save to Tauri', e);
			}
		}
	}

	reset() {
		this.webcamStream?.getTracks().forEach((t) => t.stop());
		this.webcamStream = null;
		this.webcamVideoEl = null;
		this.regionScreenshot = '';
		this.recordingState = 'ready';
		this.recordingPath = '';
		this.outputPath = '';
		this.processingProgress = 0;
		this.processingStage = '';
		this.errorMessage = '';
		this.recordingDuration = 0;
	}
}

export const appState = new AppState();

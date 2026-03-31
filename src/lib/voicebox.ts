/**
 * Frontend API client for Voicebox local TTS server.
 * Routes through Tauri IPC when in desktop mode (avoids CORS),
 * falls back to direct fetch in browser mode.
 */

import { isTauri } from './state.svelte';
import { tauriInvoke } from './tauri';

export interface VoiceboxProfile {
	id: string;
	name: string;
	language: string;
}

export interface VoiceboxModelStatus {
	model_name: string;
	display_name: string;
	downloaded: boolean;
	loaded: boolean;
}

export interface VoiceboxGeneration {
	id: string;
	status: string;
}

export class VoiceboxClient {
	constructor(private endpoint: string) {}

	/** Check if Voicebox server is reachable and healthy */
	async checkHealth(): Promise<boolean> {
		if (isTauri()) {
			try {
				return await tauriInvoke<boolean>('test_local_connection', { endpoint: this.endpoint });
			} catch {
				return false;
			}
		}
		try {
			const resp = await fetch(`${this.endpoint}/health`, {
				signal: AbortSignal.timeout(5000)
			});
			return resp.ok;
		} catch {
			return false;
		}
	}

	/** List all voice profiles */
	async listProfiles(): Promise<VoiceboxProfile[]> {
		if (isTauri()) {
			return tauriInvoke<VoiceboxProfile[]>('list_local_voices', { endpoint: this.endpoint });
		}
		const resp = await fetch(`${this.endpoint}/profiles`);
		if (!resp.ok) throw new Error(`Failed to list profiles: ${resp.status}`);
		return resp.json();
	}

	/** Get model download/load status */
	async getModelStatus(): Promise<VoiceboxModelStatus[]> {
		if (isTauri()) {
			return tauriInvoke<VoiceboxModelStatus[]>('check_model_status', { endpoint: this.endpoint });
		}
		const resp = await fetch(`${this.endpoint}/models/status`);
		if (!resp.ok) throw new Error(`Failed to get model status: ${resp.status}`);
		return resp.json();
	}

	/** Helper: JSON request routed through Tauri when available */
	private async jsonRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
		const url = `${this.endpoint}${path}`;
		if (isTauri()) {
			const result = await tauriInvoke<string>('voicebox_fetch', {
				url,
				method,
				body: body ? JSON.stringify(body) : null,
				contentType: body ? 'application/json' : null
			});
			return JSON.parse(result);
		}
		const resp = await fetch(url, {
			method,
			...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
		});
		if (!resp.ok) {
			const text = await resp.text();
			throw new Error(`${method} ${path} failed: ${resp.status} ${text}`);
		}
		return resp.json();
	}

	/** Trigger model download */
	async downloadModel(modelName: string): Promise<void> {
		await this.jsonRequest('/models/load', 'POST', { model_name: modelName });
	}

	/** Create a new voice profile */
	async createProfile(name: string, language: string): Promise<VoiceboxProfile> {
		return this.jsonRequest<VoiceboxProfile>('/profiles', 'POST', { name, language });
	}

	/** Upload reference audio sample to a profile */
	async uploadSample(
		profileId: string,
		audioFile: File,
		referenceText: string
	): Promise<unknown> {
		if (isTauri()) {
			const buffer = await audioFile.arrayBuffer();
			const fileBytes = Array.from(new Uint8Array(buffer));
			const result = await tauriInvoke<string>('voicebox_upload', {
				url: `${this.endpoint}/profiles/${profileId}/samples`,
				fileBytes,
				fileName: audioFile.name,
				fileField: 'file',
				fields: { reference_text: referenceText }
			});
			return JSON.parse(result);
		}
		const formData = new FormData();
		formData.append('file', audioFile);
		formData.append('reference_text', referenceText);
		const resp = await fetch(`${this.endpoint}/profiles/${profileId}/samples`, {
			method: 'POST',
			body: formData
		});
		if (!resp.ok) {
			const body = await resp.text();
			throw new Error(`Failed to upload sample: ${resp.status} ${body}`);
		}
		return resp.json();
	}

	/** Start a test generation */
	async testGenerate(
		profileId: string,
		text: string
	): Promise<VoiceboxGeneration> {
		return this.jsonRequest<VoiceboxGeneration>('/generate', 'POST', {
			profile_id: profileId, text, engine: 'qwen'
		});
	}

	/** Poll generation status until completed or failed */
	async pollGenerationStatus(generationId: string): Promise<string> {
		const timeout = 300_000; // 5 minutes
		const interval = 1000;
		const start = Date.now();

		while (Date.now() - start < timeout) {
			const data = await this.jsonRequest<{ status: string; error?: string }>(
				`/generate/${generationId}/status`
			);
			if (data.status === 'completed') return 'completed';
			if (data.status === 'failed') {
				throw new Error(data.error ?? 'Generation failed');
			}
			await new Promise((resolve) => setTimeout(resolve, interval));
		}

		throw new Error('Generation timed out');
	}

	/** Returns the audio URL for a completed generation */
	getAudioUrl(generationId: string): string {
		return `${this.endpoint}/audio/${generationId}`;
	}
}

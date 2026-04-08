/**
 * Frontend API client for the managed TTS sidecar.
 * All requests route through Tauri IPC to the sidecar — no direct HTTP,
 * no external Voicebox dependency.
 */

import { invoke, Channel } from '@tauri-apps/api/core';
import { tauriInvoke } from './tauri';

export interface VoiceboxProfile {
	id: string;
	name: string;
	language: string;
}

export interface VoiceboxModelStatus {
	model_name: string;
	display_name: string;
	category: 'transcription' | 'tts' | 'voice-conversion';
	recommended: boolean;
	downloaded: boolean;
	loaded: boolean;
}

export interface VoiceboxGeneration {
	id: string;
	status: string;
}

export class VoiceboxClient {
	/** Check if the TTS sidecar is running and healthy */
	async checkHealth(): Promise<boolean> {
		try {
			return await tauriInvoke<boolean>('test_local_connection');
		} catch (e) {
			console.warn('[voicebox] Health check failed:', e);
			return false;
		}
	}

	/** List all voice profiles */
	async listProfiles(): Promise<VoiceboxProfile[]> {
		return tauriInvoke<VoiceboxProfile[]>('list_local_voices');
	}

	/** Get model download/load status */
	async getModelStatus(): Promise<VoiceboxModelStatus[]> {
		return tauriInvoke<VoiceboxModelStatus[]>('check_model_status');
	}

	/** Helper: JSON request to sidecar via Tauri */
	private async jsonRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
		const result = await tauriInvoke<string>('sidecar_fetch', {
			path,
			method,
			body: body ? JSON.stringify(body) : null,
		});
		return JSON.parse(result);
	}

	/** Trigger model download via the dedicated Rust command (handles SSE parsing). */
	async downloadModel(
		modelName: string,
		onProgress?: (progress: number, status: string) => void
	): Promise<void> {
		type ModelDownloadEvent =
			| { event: 'progress'; data: { progress: number; status: string } }
			| { event: 'complete'; data: { model: string } }
			| { event: 'error'; data: { message: string } };

		const onEvent = new Channel<ModelDownloadEvent>();
		onEvent.onmessage = (msg) => {
			if (msg.event === 'progress' && onProgress) {
				onProgress(msg.data.progress, msg.data.status);
			}
		};

		await invoke('download_model', { model: modelName, onEvent });
	}

	/** Delete a downloaded model from the HuggingFace cache */
	async deleteModel(modelName: string): Promise<void> {
		await tauriInvoke('delete_model', { model: modelName });
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
		const buffer = await audioFile.arrayBuffer();
		const fileBytes = new Uint8Array(buffer);
		const result = await tauriInvoke<string>('sidecar_upload', {
			path: `/profiles/${profileId}/samples`,
			fileBytes,
			fileName: audioFile.name,
			fileField: 'audio',
			fields: { reference_text: referenceText }
		});
		return JSON.parse(result);
	}

	/** Start a test generation */
	async testGenerate(
		profileId: string,
		text: string
	): Promise<VoiceboxGeneration> {
		return this.jsonRequest<VoiceboxGeneration>('/generate', 'POST', {
			profile_id: profileId, text, language: 'en'
		});
	}

	/** Poll generation status until completed or failed.
	 *  Uses a dedicated Tauri command with a long timeout to handle
	 *  slow sidecar responses during ML inference.
	 */
	async pollGenerationStatus(generationId: string): Promise<string> {
		const timeout = 300_000; // 5 minutes
		const interval = 2000;
		const start = Date.now();

		while (Date.now() - start < timeout) {
			const data = await tauriInvoke<{ status: string; error?: string }>(
				'poll_generation',
				{ generationId }
			);
			if (data.status === 'completed') return 'completed';
			if (data.status === 'error') {
				throw new Error(data.error ?? 'Generation failed');
			}
			await new Promise((resolve) => setTimeout(resolve, interval));
		}

		throw new Error('Generation timed out');
	}

	/** Get the audio URL for a completed generation.
	 *  Fetches audio bytes via Tauri command and returns a blob: URL.
	 */
	async getAudioUrl(generationId: string): Promise<string> {
		const bytes = await tauriInvoke<number[]>('get_generation_audio', { generationId });
		const blob = new Blob([new Uint8Array(bytes)], { type: 'audio/wav' });
		return URL.createObjectURL(blob);
	}
}

export const voicebox = new VoiceboxClient();

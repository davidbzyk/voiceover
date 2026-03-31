/**
 * Frontend API client for Voicebox local TTS server.
 * Used by the Create Voice wizard to talk directly to Voicebox
 * without routing through Tauri commands.
 */

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

	/** GET {endpoint}/health -- true if server is reachable and healthy */
	async checkHealth(): Promise<boolean> {
		try {
			const resp = await fetch(`${this.endpoint}/health`, {
				signal: AbortSignal.timeout(5000)
			});
			return resp.ok;
		} catch {
			return false;
		}
	}

	/** GET {endpoint}/profiles -- list all voice profiles */
	async listProfiles(): Promise<VoiceboxProfile[]> {
		const resp = await fetch(`${this.endpoint}/profiles`);
		if (!resp.ok) throw new Error(`Failed to list profiles: ${resp.status}`);
		return resp.json();
	}

	/** GET {endpoint}/models/status -- model download/load status */
	async getModelStatus(): Promise<VoiceboxModelStatus[]> {
		const resp = await fetch(`${this.endpoint}/models/status`);
		if (!resp.ok) throw new Error(`Failed to get model status: ${resp.status}`);
		return resp.json();
	}

	/** POST {endpoint}/models/load -- trigger model download */
	async downloadModel(modelName: string): Promise<void> {
		const resp = await fetch(`${this.endpoint}/models/load`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ model_name: modelName })
		});
		if (!resp.ok) {
			const body = await resp.text();
			throw new Error(`Failed to download model: ${resp.status} ${body}`);
		}
	}

	/** POST {endpoint}/profiles -- create a new voice profile */
	async createProfile(name: string, language: string): Promise<VoiceboxProfile> {
		const resp = await fetch(`${this.endpoint}/profiles`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name, language })
		});
		if (!resp.ok) {
			const body = await resp.text();
			throw new Error(`Failed to create profile: ${resp.status} ${body}`);
		}
		return resp.json();
	}

	/** POST {endpoint}/profiles/{profileId}/samples -- upload reference audio */
	async uploadSample(
		profileId: string,
		audioFile: File,
		referenceText: string
	): Promise<unknown> {
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

	/** POST {endpoint}/generate -- start a test generation */
	async testGenerate(
		profileId: string,
		text: string
	): Promise<VoiceboxGeneration> {
		const resp = await fetch(`${this.endpoint}/generate`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ profile_id: profileId, text, engine: 'qwen' })
		});
		if (!resp.ok) {
			const body = await resp.text();
			throw new Error(`Failed to start generation: ${resp.status} ${body}`);
		}
		return resp.json();
	}

	/** Poll GET {endpoint}/generate/{id}/status until completed or failed */
	async pollGenerationStatus(generationId: string): Promise<string> {
		const timeout = 300_000; // 5 minutes
		const interval = 1000;
		const start = Date.now();

		while (Date.now() - start < timeout) {
			const resp = await fetch(`${this.endpoint}/generate/${generationId}/status`);
			if (!resp.ok) throw new Error(`Status check failed: ${resp.status}`);

			const data: { status: string; error?: string } = await resp.json();
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

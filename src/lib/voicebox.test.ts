import { describe, it, expect, vi, beforeEach } from 'vitest';
import { VoiceboxClient } from './voicebox';

vi.mock('./tauri');

import { tauriInvoke } from './tauri';

const mockedInvoke = vi.mocked(tauriInvoke);

describe('VoiceboxClient', () => {
	let client: VoiceboxClient;

	beforeEach(() => {
		vi.restoreAllMocks();
		client = new VoiceboxClient();
	});

	describe('checkHealth', () => {
		it('returns true when test_local_connection succeeds', async () => {
			mockedInvoke.mockResolvedValueOnce(true);
			const result = await client.checkHealth();
			expect(result).toBe(true);
			expect(mockedInvoke).toHaveBeenCalledWith('test_local_connection');
		});

		it('returns false and logs warning on failure', async () => {
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			mockedInvoke.mockRejectedValueOnce(new Error('connection refused'));
			const result = await client.checkHealth();
			expect(result).toBe(false);
			expect(warnSpy).toHaveBeenCalledOnce();
			expect(warnSpy.mock.calls[0][0]).toContain('[voicebox]');
		});
	});

	describe('pollGenerationStatus', () => {
		it("resolves with 'completed' when status becomes 'completed'", async () => {
			mockedInvoke.mockResolvedValueOnce({ status: 'processing' });
			mockedInvoke.mockResolvedValueOnce({ status: 'completed' });

			const result = await client.pollGenerationStatus('gen-1');
			expect(result).toBe('completed');
			expect(mockedInvoke).toHaveBeenCalledWith('poll_generation', { generationId: 'gen-1' });
		});

		it("throws on 'error' status with the error message", async () => {
			mockedInvoke.mockResolvedValueOnce({ status: 'error', error: 'Model crashed' });

			await expect(client.pollGenerationStatus('gen-2')).rejects.toThrow('Model crashed');
		});

		it("throws on 'error' status with fallback message when error field is missing", async () => {
			mockedInvoke.mockResolvedValueOnce({ status: 'error' });

			await expect(client.pollGenerationStatus('gen-3')).rejects.toThrow('Generation failed');
		});

		it('times out after max duration', async () => {
			let now = 0;
			vi.spyOn(Date, 'now').mockImplementation(() => now);

			mockedInvoke.mockImplementation(async () => {
				// Each poll advances time past the 5-minute timeout
				now += 300_001;
				return { status: 'processing' };
			});

			await expect(client.pollGenerationStatus('gen-4')).rejects.toThrow(
				'Generation timed out'
			);
		});
	});

	describe('getAudioUrl', () => {
		it('fetches audio bytes and returns a blob URL', async () => {
			const fakeBytes = [0x52, 0x49, 0x46, 0x46]; // RIFF header
			mockedInvoke.mockResolvedValueOnce(fakeBytes);

			const url = await client.getAudioUrl('gen-99');
			expect(url).toMatch(/^blob:/);
			expect(mockedInvoke).toHaveBeenCalledWith('get_generation_audio', {
				generationId: 'gen-99'
			});
		});

		it('throws when command fails', async () => {
			mockedInvoke.mockRejectedValueOnce(new Error('TTS sidecar is not running'));

			await expect(client.getAudioUrl('gen-99')).rejects.toThrow(
				'TTS sidecar is not running'
			);
		});
	});

	describe('getModelStatus', () => {
		it('invokes the check_model_status command', async () => {
			const mockStatus = [
				{ model_name: 'qwen-tts', display_name: 'Qwen TTS', downloaded: true, loaded: false }
			];
			mockedInvoke.mockResolvedValueOnce(mockStatus);

			const result = await client.getModelStatus();
			expect(result).toEqual(mockStatus);
			expect(mockedInvoke).toHaveBeenCalledWith('check_model_status');
		});

		it('returns expanded model status with category and recommended fields', async () => {
			const mockStatus = [
				{
					model_name: 'whisper-large-v3-turbo',
					display_name: 'Whisper Large v3 Turbo',
					category: 'transcription',
					recommended: true,
					downloaded: true,
					loaded: true
				},
				{
					model_name: 'qwen-tts-1.7B',
					display_name: 'Qwen TTS 1.7B',
					category: 'tts',
					recommended: false,
					downloaded: false,
					loaded: false
				},
				{
					model_name: 'cosyvoice3-0.5B',
					display_name: 'CosyVoice3 0.5B',
					category: 'voice-conversion',
					recommended: false,
					downloaded: true,
					loaded: false
				}
			];
			mockedInvoke.mockResolvedValueOnce(mockStatus);

			const result = await client.getModelStatus();
			expect(result).toHaveLength(3);

			// Verify category field is present and valid
			const categories = result.map((m: any) => m.category);
			expect(categories).toContain('transcription');
			expect(categories).toContain('tts');
			expect(categories).toContain('voice-conversion');

			// Verify recommended field is present and boolean
			for (const model of result) {
				expect(typeof (model as any).recommended).toBe('boolean');
			}

			// Verify the recommended model is whisper-large-v3-turbo
			const recommended = result.find((m: any) => m.recommended);
			expect(recommended).toBeDefined();
			expect((recommended as any).model_name).toBe('whisper-large-v3-turbo');
		});
	});

	describe('deleteModel', () => {
		it('invokes the delete_model command with model name', async () => {
			mockedInvoke.mockResolvedValueOnce(undefined);

			await client.deleteModel('whisper-small');
			expect(mockedInvoke).toHaveBeenCalledWith('delete_model', { model: 'whisper-small' });
		});

		it('propagates errors from Tauri layer', async () => {
			mockedInvoke.mockRejectedValueOnce(new Error('Model not found'));

			await expect(client.deleteModel('nonexistent')).rejects.toThrow('Model not found');
		});
	});

	describe('listProfiles', () => {
		it('invokes the list_local_voices command', async () => {
			const mockProfiles = [{ id: 'p1', name: 'Test Voice', language: 'en' }];
			mockedInvoke.mockResolvedValueOnce(mockProfiles);

			const result = await client.listProfiles();
			expect(result).toEqual(mockProfiles);
			expect(mockedInvoke).toHaveBeenCalledWith('list_local_voices');
		});
	});
});

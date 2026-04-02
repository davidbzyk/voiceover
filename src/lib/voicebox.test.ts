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
		it('constructs correct URL from port and generation ID', async () => {
			mockedInvoke.mockResolvedValueOnce({ port: 8123 });

			const url = await client.getAudioUrl('gen-99');
			expect(url).toBe('http://127.0.0.1:8123/audio/gen-99');
			expect(mockedInvoke).toHaveBeenCalledWith('get_sidecar_status');
		});

		it('throws when sidecar not running (port not available)', async () => {
			mockedInvoke.mockResolvedValueOnce({ port: null });

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

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { libraryState, type RecordingInfo, type RecordingMeta } from './library.svelte';

// Mock tauriInvoke
vi.mock('./tauri', () => ({
	tauriInvoke: vi.fn()
}));

// Mock isTauri — default to true for most tests
vi.mock('./state.svelte', () => ({
	isTauri: vi.fn(() => true),
	appState: {
		config: {
			google_drive: { connected: false },
			output_dir: '/Users/test/Movies/VoiceOver'
		}
	}
}));

import { tauriInvoke } from './tauri';
import { isTauri } from './state.svelte';

const mockInvoke = vi.mocked(tauriInvoke);
const mockIsTauri = vi.mocked(isTauri);

function makeRecording(overrides: Partial<RecordingInfo> = {}): RecordingInfo {
	return {
		path: '/test/voiceover-1740000000.mp4',
		filename: 'voiceover-1740000000.mp4',
		sizeBytes: 1024 * 1024,
		createdAt: 1740000000,
		durationSecs: null,
		thumbnailPath: null,
		meta: null,
		...overrides
	};
}

describe('LibraryState.load', () => {
	beforeEach(() => {
		libraryState.recordings = [];
		libraryState.error = '';
		mockIsTauri.mockReturnValue(true);
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	it('populates recordings from list_recordings command', async () => {
		const recordings = [
			makeRecording({ filename: 'voiceover-1740000001.mp4', createdAt: 1740000001 }),
			makeRecording({ filename: 'voiceover-1740000000.mp4', createdAt: 1740000000 })
		];
		mockInvoke.mockResolvedValue(recordings);

		await libraryState.load();

		expect(mockInvoke).toHaveBeenCalledWith('list_recordings');
		expect(libraryState.recordings).toHaveLength(2);
		expect(libraryState.recordings[0].filename).toBe('voiceover-1740000001.mp4');
	});

	it('sets error on invoke failure', async () => {
		mockInvoke.mockRejectedValue(new Error('Sidecar not running'));

		await libraryState.load();

		expect(libraryState.error).toContain('Sidecar not running');
		expect(libraryState.recordings).toEqual([]);
	});

	it('sets error when not in Tauri', async () => {
		mockIsTauri.mockReturnValue(false);

		await libraryState.load();

		expect(libraryState.error).toContain('desktop app');
		expect(libraryState.recordings).toEqual([]);
	});

	it('clears loading flag after success', async () => {
		mockInvoke.mockResolvedValue([]);

		await libraryState.load();

		expect(libraryState.loading).toBe(false);
	});

	it('clears loading flag after failure', async () => {
		mockInvoke.mockRejectedValue(new Error('fail'));

		await libraryState.load();

		expect(libraryState.loading).toBe(false);
	});
});

describe('LibraryState.sorted', () => {
	const older = makeRecording({ path: '/old.mp4', filename: 'old.mp4', createdAt: 1000, sizeBytes: 500 });
	const newer = makeRecording({ path: '/new.mp4', filename: 'new.mp4', createdAt: 2000, sizeBytes: 100 });
	const biggest = makeRecording({ path: '/big.mp4', filename: 'big.mp4', createdAt: 1500, sizeBytes: 9999 });

	beforeEach(() => {
		libraryState.recordings = [older, newer, biggest];
		libraryState.sortBy = 'date';
		libraryState.sortDir = 'desc';
	});

	it('sorts by date descending by default', () => {
		expect(libraryState.sorted[0].filename).toBe('new.mp4');
		expect(libraryState.sorted[2].filename).toBe('old.mp4');
	});

	it('sorts by date ascending', () => {
		libraryState.sortDir = 'asc';
		expect(libraryState.sorted[0].filename).toBe('old.mp4');
		expect(libraryState.sorted[2].filename).toBe('new.mp4');
	});

	it('sorts by size descending', () => {
		libraryState.sortBy = 'size';
		libraryState.sortDir = 'desc';
		expect(libraryState.sorted[0].filename).toBe('big.mp4');
		expect(libraryState.sorted[2].filename).toBe('new.mp4');
	});

	it('sorts by name ascending', () => {
		libraryState.sortBy = 'name';
		libraryState.sortDir = 'asc';
		expect(libraryState.sorted[0].filename).toBe('big.mp4');
		expect(libraryState.sorted[2].filename).toBe('old.mp4');
	});
});

describe('LibraryState.setSortBy', () => {
	beforeEach(() => {
		libraryState.sortBy = 'date';
		libraryState.sortDir = 'desc';
	});

	it('switches sort field and resets direction', () => {
		libraryState.setSortBy('size');
		expect(libraryState.sortBy).toBe('size');
		expect(libraryState.sortDir).toBe('desc');
	});

	it('toggles direction when same field clicked', () => {
		libraryState.setSortBy('date');
		expect(libraryState.sortDir).toBe('asc');

		libraryState.setSortBy('date');
		expect(libraryState.sortDir).toBe('desc');
	});

	it('defaults to ascending for name sort', () => {
		libraryState.setSortBy('name');
		expect(libraryState.sortDir).toBe('asc');
	});
});

describe('LibraryState.totalSize', () => {
	it('sums all recording sizes', () => {
		libraryState.recordings = [
			makeRecording({ sizeBytes: 1000 }),
			makeRecording({ path: '/b.mp4', sizeBytes: 2500 }),
			makeRecording({ path: '/c.mp4', sizeBytes: 500 })
		];
		expect(libraryState.totalSize).toBe(4000);
	});

	it('returns 0 for empty recordings', () => {
		libraryState.recordings = [];
		expect(libraryState.totalSize).toBe(0);
	});
});

describe('LibraryState.deleteRecording', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('calls delete command and removes from local list', async () => {
		mockInvoke.mockResolvedValue(undefined);
		libraryState.recordings = [
			makeRecording({ path: '/a.mp4' }),
			makeRecording({ path: '/b.mp4' })
		];

		await libraryState.deleteRecording('/a.mp4');

		expect(mockInvoke).toHaveBeenCalledWith('delete_recording', { filePath: '/a.mp4' });
		expect(libraryState.recordings).toHaveLength(1);
		expect(libraryState.recordings[0].path).toBe('/b.mp4');
	});

	it('propagates errors from delete command', async () => {
		mockInvoke.mockRejectedValue(new Error('Access denied'));
		libraryState.recordings = [makeRecording({ path: '/a.mp4' })];

		await expect(libraryState.deleteRecording('/a.mp4')).rejects.toThrow('Access denied');
		// Recording should still be in list since delete failed
		expect(libraryState.recordings).toHaveLength(1);
	});
});

describe('LibraryState.updateRecordingMeta', () => {
	it('updates meta for matching recording', () => {
		libraryState.recordings = [
			makeRecording({ path: '/a.mp4', meta: { voiceProfile: 'MJ', provider: 'local', driveUrl: null, uploadedAt: null, voiceReplacement: true } })
		];

		libraryState.updateRecordingMeta('/a.mp4', { driveUrl: 'https://drive.google.com/file/123' });

		expect(libraryState.recordings[0].meta?.driveUrl).toBe('https://drive.google.com/file/123');
		expect(libraryState.recordings[0].meta?.voiceProfile).toBe('MJ');
	});

	it('creates meta with defaults when recording had no meta', () => {
		libraryState.recordings = [makeRecording({ path: '/a.mp4', meta: null })];

		libraryState.updateRecordingMeta('/a.mp4', { driveUrl: 'https://drive.google.com/file/456' });

		expect(libraryState.recordings[0].meta?.driveUrl).toBe('https://drive.google.com/file/456');
		expect(libraryState.recordings[0].meta?.voiceReplacement).toBe(false);
	});

	it('does not modify other recordings', () => {
		libraryState.recordings = [
			makeRecording({ path: '/a.mp4' }),
			makeRecording({ path: '/b.mp4' })
		];

		libraryState.updateRecordingMeta('/a.mp4', { driveUrl: 'https://drive.google.com/file/789' });

		expect(libraryState.recordings[1].meta).toBeNull();
	});
});

describe('LibraryState.openInSystem / revealInFinder', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('passes path to open_in_system command', async () => {
		mockInvoke.mockResolvedValue(undefined);

		await libraryState.openInSystem('/test/video.mp4');

		expect(mockInvoke).toHaveBeenCalledWith('open_in_system', { path: '/test/video.mp4' });
	});

	it('passes path to reveal_in_finder command', async () => {
		mockInvoke.mockResolvedValue(undefined);

		await libraryState.revealInFinder('/test/video.mp4');

		expect(mockInvoke).toHaveBeenCalledWith('reveal_in_finder', { path: '/test/video.mp4' });
	});
});

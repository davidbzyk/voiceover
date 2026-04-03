import { tauriInvoke } from './tauri';
import { isTauri } from './state.svelte';
import { logger } from './logger';

export type RecordingMeta = {
	voiceProfile: string | null;
	provider: string | null;
	driveUrl: string | null;
	uploadedAt: number | null;
	voiceReplacement: boolean;
};

export type RecordingInfo = {
	path: string;
	filename: string;
	sizeBytes: number;
	createdAt: number;
	durationSecs: number | null;
	thumbnailPath: string | null;
	meta: RecordingMeta | null;
};

class LibraryState {
	recordings = $state<RecordingInfo[]>([]);
	loading = $state(false);
	sortBy = $state<'date' | 'size' | 'name'>('date');
	sortDir = $state<'desc' | 'asc'>('desc');

	sorted = $derived.by(() => {
		const sorted = [...this.recordings];
		const dir = this.sortDir === 'asc' ? 1 : -1;
		switch (this.sortBy) {
			case 'date':
				sorted.sort((a, b) => dir * (a.createdAt - b.createdAt));
				break;
			case 'size':
				sorted.sort((a, b) => dir * (a.sizeBytes - b.sizeBytes));
				break;
			case 'name':
				sorted.sort((a, b) => dir * a.filename.localeCompare(b.filename));
				break;
		}
		return sorted;
	});

	totalSize = $derived(this.recordings.reduce((sum, r) => sum + r.sizeBytes, 0));

	error = $state('');

	async load() {
		if (!isTauri()) {
			this.error = 'Library requires the desktop app';
			return;
		}
		this.loading = true;
		this.error = '';
		try {
			this.recordings = await tauriInvoke<RecordingInfo[]>('list_recordings');
		} catch (err) {
			logger.error('library', 'Failed to load recordings', err);
			this.error = 'Could not load recordings. Check output directory in Settings.';
			this.recordings = [];
		} finally {
			this.loading = false;
		}
	}

	async deleteRecording(path: string) {
		await tauriInvoke('delete_recording', { filePath: path });
		this.recordings = this.recordings.filter((r) => r.path !== path);
	}

	async openInSystem(path: string) {
		await tauriInvoke('open_in_system', { path });
	}

	async revealInFinder(path: string) {
		await tauriInvoke('reveal_in_finder', { path });
	}

	async renameRecording(path: string, newName: string): Promise<RecordingInfo> {
		const updated = await tauriInvoke<RecordingInfo>('rename_recording', { filePath: path, newName });
		this.recordings = this.recordings.map((r) => (r.path === path ? updated : r));
		return updated;
	}

	updateRecordingMeta(path: string, updates: Partial<RecordingMeta>) {
		this.recordings = this.recordings.map((r) =>
			r.path === path
				? { ...r, meta: { ...r.meta, voiceProfile: null, provider: null, driveUrl: null, uploadedAt: null, voiceReplacement: false, ...r.meta, ...updates } }
				: r
		);
	}

	setSortBy(sort: 'date' | 'size' | 'name') {
		if (this.sortBy === sort) {
			this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			this.sortBy = sort;
			this.sortDir = sort === 'name' ? 'asc' : 'desc';
		}
	}
}

export const libraryState = new LibraryState();

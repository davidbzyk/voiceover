import { tauriInvoke } from './tauri';
import { isTauri } from './state.svelte';

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
			this.error = 'Library requires the desktop app (pnpm tauri dev)';
			return;
		}
		this.loading = true;
		this.error = '';
		try {
			const results = await tauriInvoke<RecordingInfo[]>('list_recordings');
			console.log('[library] Loaded recordings:', results.length);
			this.recordings = results;
			if (results.length === 0) {
				// Check if the output dir might be wrong by importing appState
				const { appState } = await import('./state.svelte');
				if (appState.config.output_dir) {
					console.log('[library] Output dir:', appState.config.output_dir);
				}
			}
		} catch (err) {
			console.error('[library] Failed to load recordings:', err);
			this.error = String(err);
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

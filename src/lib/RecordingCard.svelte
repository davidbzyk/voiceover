<script lang="ts">
	import { onMount } from 'svelte';
	import { tauriInvoke } from '$lib/tauri';
	import { appState, isTauri } from '$lib/state.svelte';
	import { refreshDriveToken } from '$lib/drive';
	import { libraryState, type RecordingInfo } from '$lib/library.svelte';
	import { logger } from '$lib/logger';

	let { recording }: { recording: RecordingInfo } = $props();

	let thumbnailUrl = $state<string>('');
	let thumbnailLoading = $state(false);
	let confirmingDelete = $state(false);
	let uploading = $state(false);
	let errorMessage = $state('');
	let cardEl = $state<HTMLDivElement | null>(null);

	const alreadyUploaded = $derived(!!recording.meta?.driveUrl);
	const driveConnected = $derived(appState.config.google_drive.connected);

	const formattedDate = $derived.by(() => {
		if (!recording.createdAt) return 'Unknown date';
		const date = new Date(recording.createdAt * 1000);
		return date.toLocaleDateString('en-US', {
			month: 'short', day: 'numeric', year: 'numeric',
			hour: 'numeric', minute: '2-digit'
		});
	});

	const formattedSize = $derived.by(() => {
		const bytes = recording.sizeBytes;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	});

	async function loadThumbnail() {
		if (!isTauri() || thumbnailLoading || thumbnailUrl) return;
		thumbnailLoading = true;
		try {
			const thumbPath = await tauriInvoke<string>('generate_thumbnail', {
				filePath: recording.path
			});
			const bytes = await tauriInvoke<number[]>('read_file_bytes', { path: thumbPath });
			const blob = new Blob([new Uint8Array(bytes)], { type: 'image/jpeg' });
			thumbnailUrl = URL.createObjectURL(blob);
		} catch (err) {
			logger.error('library', 'Failed to load thumbnail', err);
		} finally {
			thumbnailLoading = false;
		}
	}

	onMount(() => {
		if (!cardEl) return;
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) {
					loadThumbnail();
					observer.disconnect();
				}
			},
			{ threshold: 0.1 }
		);
		observer.observe(cardEl);
		return () => {
			observer.disconnect();
			if (thumbnailUrl) URL.revokeObjectURL(thumbnailUrl);
		};
	});

	async function handleDelete() {
		if (!confirmingDelete) {
			confirmingDelete = true;
			return;
		}
		errorMessage = '';
		try {
			await libraryState.deleteRecording(recording.path);
		} catch (err) {
			errorMessage = `Delete failed: ${err}`;
			logger.error('library', 'Failed to delete recording', err);
		}
		confirmingDelete = false;
	}

	async function handleUploadToDrive() {
		if (uploading || alreadyUploaded || !driveConnected) return;
		uploading = true;
		errorMessage = '';
		try {
			let token = appState.config.google_drive.access_token;
			const now = Math.floor(Date.now() / 1000);
			if (!appState.config.google_drive.expires_at || now >= appState.config.google_drive.expires_at) {
				token = await refreshDriveToken();
			}

			const { invoke, Channel } = await import('@tauri-apps/api/core');
			type DriveEvent =
				| { event: 'progress'; data: { percent: number } }
				| { event: 'complete'; data: { url: string } }
				| { event: 'error'; data: { message: string } };

			const onEvent = new Channel<DriveEvent>();
			let driveUrl = '';
			onEvent.onmessage = (msg) => {
				if (msg.event === 'complete') driveUrl = msg.data.url;
			};

			driveUrl = await invoke<string>('upload_to_drive', {
				accessToken: token,
				filePath: recording.path,
				onEvent
			});

			if (driveUrl) {
				libraryState.updateRecordingMeta(recording.path, { driveUrl });
			}
		} catch (err) {
			errorMessage = `Upload failed: ${err}`;
			logger.error('library', 'Drive upload failed', err);
		} finally {
			uploading = false;
		}
	}

	async function handleOpen() {
		try {
			await libraryState.openInSystem(recording.path);
		} catch (err) {
			errorMessage = `Could not open: ${err}`;
			logger.error('library', 'Failed to open recording', err);
		}
	}

	async function handleReveal() {
		try {
			await libraryState.revealInFinder(recording.path);
		} catch (err) {
			errorMessage = `Could not reveal: ${err}`;
			logger.error('library', 'Failed to reveal in Finder', err);
		}
	}
</script>

<div class="recording-card" bind:this={cardEl}>
	<div class="thumbnail">
		{#if thumbnailUrl}
			<img src={thumbnailUrl} alt="Thumbnail for {recording.filename}" />
		{:else if thumbnailLoading}
			<div class="thumb-placeholder">...</div>
		{:else}
			<div class="thumb-placeholder">🎬</div>
		{/if}
	</div>

	<div class="info">
		<div class="filename" title={recording.filename}>{recording.filename}</div>
		<div class="meta-row">
			<span>{formattedDate}</span>
			<span>·</span>
			<span>{formattedSize}</span>
		</div>
		{#if recording.meta}
			<div class="meta-row">
				{#if recording.meta.voiceProfile}
					<span class="voice-badge">🎤 {recording.meta.voiceProfile}</span>
				{/if}
				{#if recording.meta.driveUrl}
					<a href={recording.meta.driveUrl} target="_blank" rel="noopener" class="drive-badge uploaded">
						☁️ Uploaded
					</a>
				{/if}
			</div>
		{/if}
		{#if errorMessage}
			<div class="card-error">{errorMessage}</div>
		{/if}
	</div>

	<div class="actions">
		<button class="action-btn" onclick={handleOpen} title="Play">
			▶
		</button>
		{#if driveConnected}
			{#if alreadyUploaded}
				<a href={recording.meta?.driveUrl} target="_blank" rel="noopener" class="action-btn uploaded" title="View on Drive">
					☁️
				</a>
			{:else}
				<button
					class="action-btn"
					onclick={handleUploadToDrive}
					disabled={uploading}
					title={uploading ? 'Uploading...' : 'Upload to Drive'}
				>
					{uploading ? '⏳' : '☁️'}
				</button>
			{/if}
		{/if}
		<button class="action-btn" onclick={handleReveal} title="Show in Finder">
			📂
		</button>
		<button
			class="action-btn"
			class:danger={confirmingDelete}
			onclick={handleDelete}
			onmouseleave={() => (confirmingDelete = false)}
			title={confirmingDelete ? 'Click again to confirm' : 'Delete'}
		>
			{confirmingDelete ? '⚠️' : '🗑️'}
		</button>
	</div>
</div>

<style>
	.recording-card {
		display: flex;
		gap: 14px;
		padding: 14px;
		background: #1e293b;
		border-radius: 8px;
		align-items: center;
	}
	.recording-card:hover {
		background: #263548;
	}
	.thumbnail {
		width: 120px;
		height: 68px;
		border-radius: 6px;
		overflow: hidden;
		background: #0f172a;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.thumbnail img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.thumb-placeholder {
		color: #475569;
		font-size: 20px;
	}
	.info {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.filename {
		font-size: 13px;
		font-weight: 500;
		color: #f1f5f9;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.meta-row {
		display: flex;
		gap: 6px;
		font-size: 11px;
		color: #94a3b8;
		align-items: center;
		flex-wrap: wrap;
	}
	.voice-badge {
		background: #334155;
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 10px;
	}
	.drive-badge {
		font-size: 10px;
		text-decoration: none;
	}
	.drive-badge.uploaded {
		color: #22c55e;
	}
	.actions {
		display: flex;
		gap: 4px;
		flex-shrink: 0;
	}
	.action-btn {
		width: 32px;
		height: 32px;
		border: none;
		background: #334155;
		border-radius: 6px;
		cursor: pointer;
		font-size: 14px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s;
	}
	.action-btn:hover {
		background: #475569;
	}
	.card-error {
		font-size: 10px;
		color: #ef4444;
	}
	.action-btn.uploaded {
		color: #22c55e;
		text-decoration: none;
	}
	.action-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.action-btn.danger {
		background: #7f1d1d;
	}
	.action-btn.danger:hover {
		background: #991b1b;
	}
</style>

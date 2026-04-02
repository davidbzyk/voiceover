<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { appState } from '$lib/state.svelte';
	import { libraryState } from '$lib/library.svelte';
	import RecordingCard from '$lib/RecordingCard.svelte';

	const sortOptions: { value: 'date' | 'size' | 'name'; label: string }[] = [
		{ value: 'date', label: 'Date' },
		{ value: 'size', label: 'Size' },
		{ value: 'name', label: 'Name' }
	];

	const formattedTotalSize = $derived(() => {
		const bytes = libraryState.totalSize;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
		return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
	});

	onMount(() => {
		if (appState.libraryStale || libraryState.recordings.length === 0) {
			libraryState.load();
			appState.libraryStale = false;
		}
	});
</script>

<div class="library">
	<div class="library-header">
		<div>
			<h2>Library</h2>
			<div class="output-dir">{appState.config.output_dir}</div>
		</div>
		<div class="header-actions">
			<button class="small-btn" onclick={() => libraryState.load()}>↻ Refresh</button>
		</div>
	</div>

	<div class="sort-bar">
		{#each sortOptions as opt}
			<button
				class="sort-btn"
				class:active={libraryState.sortBy === opt.value}
				onclick={() => libraryState.setSortBy(opt.value)}
			>
				{opt.label}
				{#if libraryState.sortBy === opt.value}
					<span class="sort-arrow">{libraryState.sortDir === 'asc' ? '↑' : '↓'}</span>
				{/if}
			</button>
		{/each}
	</div>

	{#if libraryState.error}
		<div class="empty-state">
			<div class="status invalid">{libraryState.error}</div>
			<button class="small-btn" onclick={() => libraryState.load()}>Retry</button>
		</div>
	{:else if libraryState.loading}
		<div class="empty-state">Loading recordings...</div>
	{:else if libraryState.sorted.length === 0}
		<div class="empty-state">
			<div class="empty-icon">📁</div>
			<div>No recordings found</div>
			<div class="empty-hint">Scanning: {appState.config.output_dir}</div>
			<div class="empty-actions">
				<button class="small-btn accent" onclick={() => goto('/')}>Start Recording</button>
				<button class="small-btn" onclick={() => goto('/settings')}>Check Output Dir</button>
			</div>
		</div>
	{:else}
		<div class="recordings-list">
			{#each libraryState.sorted as recording (recording.path)}
				<RecordingCard {recording} />
			{/each}
		</div>

		<div class="footer">
			{libraryState.recordings.length} recording{libraryState.recordings.length === 1 ? '' : 's'} · {formattedTotalSize()} total
		</div>
	{/if}
</div>

<style>
	.library {
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 16px;
		flex: 1;
	}
	.library-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
	}
	.library-header h2 {
		margin: 0;
		font-size: 18px;
	}
	.output-dir {
		font-size: 11px;
		color: #64748b;
		margin-top: 4px;
	}
	.header-actions {
		display: flex;
		gap: 8px;
	}
	.sort-bar {
		display: flex;
		gap: 4px;
		background: #0f172a;
		border-radius: 6px;
		padding: 3px;
		align-self: flex-start;
	}
	.sort-btn {
		background: transparent;
		border: none;
		color: #64748b;
		padding: 6px 12px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 12px;
		font-weight: 500;
		transition: all 0.15s;
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.sort-btn.active {
		background: #334155;
		color: #f1f5f9;
	}
	.sort-btn:hover:not(.active) {
		color: #94a3b8;
	}
	.sort-arrow {
		font-size: 10px;
	}
	.recordings-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
		flex: 1;
		overflow-y: auto;
	}
	.empty-state {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		color: #64748b;
		font-size: 14px;
	}
	.empty-icon {
		font-size: 40px;
	}
	.empty-hint {
		font-size: 11px;
		color: #475569;
		font-family: monospace;
	}
	.empty-actions {
		display: flex;
		gap: 8px;
	}
	.footer {
		font-size: 11px;
		color: #64748b;
		text-align: center;
		padding-top: 8px;
		border-top: 1px solid #1e293b;
	}
</style>

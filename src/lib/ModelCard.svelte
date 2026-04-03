<script lang="ts">
	import type { VoiceboxModelStatus } from '$lib/voicebox';

	interface Props {
		model: VoiceboxModelStatus;
		downloadingModel: string | null;
		downloadProgress: string;
		confirmingDelete: string | null;
		deletingModel: string | null;
		activeModelName?: string;
		onSelect?: (modelName: string) => void;
		onDownload: (modelName: string) => void;
		onConfirmDelete: (modelName: string) => void;
		onCancelDelete: () => void;
		onDelete: (modelName: string) => void;
	}

	let {
		model,
		downloadingModel,
		downloadProgress,
		confirmingDelete,
		deletingModel,
		activeModelName,
		onSelect,
		onDownload,
		onConfirmDelete,
		onCancelDelete,
		onDelete,
	}: Props = $props();
</script>

<div class="model-row">
	<div class="model-info">
		<div class="model-name">
			{model.display_name}
			{#if model.recommended}
				<span class="recommended-badge">Recommended</span>
			{/if}
		</div>
		<div class="model-status-text">
			{model.downloaded ? 'Downloaded' : 'Not downloaded'}
		</div>
	</div>
	<div class="model-actions">
		{#if model.downloaded}
			{#if onSelect && activeModelName !== undefined}
				<button
					class="radio-btn"
					class:active={activeModelName === model.model_name}
					onclick={() => onSelect(model.model_name)}
					title="Use this model"
				>
					{activeModelName === model.model_name ? '● Active' : '○ Select'}
				</button>
			{/if}
			{#if confirmingDelete === model.model_name}
				<button
					class="small-btn danger"
					onclick={() => onDelete(model.model_name)}
					disabled={deletingModel === model.model_name}
				>
					{deletingModel === model.model_name ? 'Deleting...' : 'Confirm'}
				</button>
				<button class="small-btn" onclick={onCancelDelete}>Cancel</button>
			{:else}
				<button
					class="small-btn danger-outline"
					onclick={() => onConfirmDelete(model.model_name)}
				>
					Delete
				</button>
			{/if}
		{:else if downloadingModel === model.model_name}
			<span class="download-status">{downloadProgress}</span>
		{:else}
			<button
				class="small-btn accent"
				onclick={() => onDownload(model.model_name)}
				disabled={downloadingModel !== null}
			>
				Download
			</button>
		{/if}
	</div>
</div>

<style>
	.model-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 10px 0;
		border-bottom: 1px solid #334155;
	}
	.model-row:last-child {
		border-bottom: none;
	}
	.model-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.model-name {
		font-size: 13px;
		color: #e2e8f0;
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.model-status-text {
		font-size: 10px;
		color: #64748b;
	}
	.model-actions {
		display: flex;
		gap: 6px;
		align-items: center;
	}
	.recommended-badge {
		font-size: 9px;
		background: rgba(99, 102, 241, 0.15);
		color: #818cf8;
		padding: 1px 6px;
		border-radius: 3px;
		font-weight: 500;
	}
	.radio-btn {
		background: none;
		border: 1px solid #475569;
		color: #94a3b8;
		font-size: 10px;
		padding: 3px 8px;
		border-radius: 4px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.radio-btn.active {
		border-color: #6366f1;
		color: #a5b4fc;
		background: rgba(99, 102, 241, 0.1);
	}
	.small-btn {
		padding: 4px 10px;
		border: 1px solid #334155;
		border-radius: 4px;
		background: transparent;
		color: #94a3b8;
		font-size: 11px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.small-btn:hover {
		color: #cbd5e1;
		border-color: #475569;
	}
	.small-btn.accent {
		border-color: #f97316;
		color: #f97316;
	}
	.small-btn.accent:hover {
		background: rgba(249, 115, 22, 0.1);
	}
	.small-btn.danger {
		color: #ef4444;
		border-color: #ef4444;
	}
	.small-btn.danger-outline {
		color: #94a3b8;
		border-color: #475569;
	}
	.small-btn.danger-outline:hover {
		color: #ef4444;
		border-color: #ef4444;
	}
	.download-status {
		font-size: 10px;
		color: #94a3b8;
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>

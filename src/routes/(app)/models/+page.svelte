<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState } from '$lib/state.svelte';
	import { logger } from '$lib/logger';
	import { VoiceboxClient, type VoiceboxModelStatus } from '$lib/voicebox';
	import { onMount } from 'svelte';

	let modelStatuses = $state<VoiceboxModelStatus[]>([]);
	let modelsLoading = $state(false);
	let modelsError = $state('');
	let downloadingModel = $state<string | null>(null);
	let downloadProgress = $state('');
	let confirmingDelete = $state<string | null>(null);
	let deletingModel = $state<string | null>(null);

	function getClient(): VoiceboxClient {
		return new VoiceboxClient();
	}

	async function loadModelStatuses() {
		modelsLoading = true;
		modelsError = '';
		try {
			modelStatuses = await getClient().getModelStatus();
		} catch (err) {
			modelsError = 'Failed to check model status. Is the TTS engine running?';
			logger.error('models', 'Failed to load model statuses', err);
		}
		modelsLoading = false;
	}

	async function handleDownloadModel(modelName: string) {
		downloadingModel = modelName;
		downloadProgress = 'Starting download...';
		try {
			await getClient().downloadModel(modelName, (_progress, status) => {
				downloadProgress = status;
			});
			downloadProgress = '';
			await loadModelStatuses();
		} catch (err) {
			downloadProgress = '';
			modelsError = `Download failed: ${err}`;
		}
		downloadingModel = null;
	}

	async function handleDeleteModel(modelName: string) {
		deletingModel = modelName;
		try {
			await getClient().deleteModel(modelName);
			// If we deleted the active whisper model, select another downloaded one
			if (modelName === appState.config.whisper_model) {
				const otherWhisper = modelStatuses.find(
					(m) => m.category === 'transcription' && m.downloaded && m.model_name !== modelName
				);
				appState.config.whisper_model = otherWhisper?.model_name ?? 'whisper-large-v3-turbo';
				await appState.saveConfig();
			}
			await loadModelStatuses();
		} catch (err) {
			modelsError = `Delete failed: ${err}`;
		}
		deletingModel = null;
		confirmingDelete = null;
	}

	async function selectWhisperModel(modelName: string) {
		appState.config.whisper_model = modelName;
		await appState.saveConfig();
	}

	onMount(() => {
		loadModelStatuses();
	});
</script>

<div class="models-page">
	<div class="header">
		<h2>Models</h2>
	</div>

	{#if modelsLoading}
		<div class="section">
			<div class="hint-text">Loading model status...</div>
		</div>
	{:else if modelsError}
		<div class="section">
			<div class="status invalid">{modelsError}</div>
			<button class="small-btn" onclick={loadModelStatuses}>Retry</button>
		</div>
	{:else}
		<!-- Transcription (Whisper) -->
		<div class="section">
			<div class="section-title">Transcription</div>
			<div class="card">
				<div class="hint-text" style="margin-bottom: 8px">
					Whisper converts speech to text. Larger models are more accurate but use more memory.
				</div>
				{#each modelStatuses.filter((m) => m.category === 'transcription') as model}
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
								<button
									class="radio-btn"
									class:active={appState.config.whisper_model === model.model_name}
									onclick={() => selectWhisperModel(model.model_name)}
									title="Use this model"
								>
									{appState.config.whisper_model === model.model_name ? '● Active' : '○ Select'}
								</button>
								{#if confirmingDelete === model.model_name}
									<button
										class="small-btn danger"
										onclick={() => handleDeleteModel(model.model_name)}
										disabled={deletingModel === model.model_name}
									>
										{deletingModel === model.model_name ? 'Deleting...' : 'Confirm'}
									</button>
									<button class="small-btn" onclick={() => (confirmingDelete = null)}>Cancel</button>
								{:else}
									<button class="small-btn danger-outline" onclick={() => (confirmingDelete = model.model_name)}>
										Delete
									</button>
								{/if}
							{:else if downloadingModel === model.model_name}
								<span class="download-status">{downloadProgress}</span>
							{:else}
								<button
									class="small-btn accent"
									onclick={() => handleDownloadModel(model.model_name)}
									disabled={downloadingModel !== null}
								>
									Download
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- Text-to-Speech (Qwen) -->
		<div class="section">
			<div class="section-title">Text-to-Speech</div>
			<div class="card">
				<div class="hint-text" style="margin-bottom: 8px">
					Qwen generates speech from text using your cloned voice.
				</div>
				{#each modelStatuses.filter((m) => m.category === 'tts') as model}
					<div class="model-row">
						<div class="model-info">
							<div class="model-name">{model.display_name}</div>
							<div class="model-status-text">
								{model.downloaded ? 'Downloaded' : 'Not downloaded'}
							</div>
						</div>
						<div class="model-actions">
							{#if model.downloaded}
								{#if confirmingDelete === model.model_name}
									<button
										class="small-btn danger"
										onclick={() => handleDeleteModel(model.model_name)}
										disabled={deletingModel === model.model_name}
									>
										{deletingModel === model.model_name ? 'Deleting...' : 'Confirm'}
									</button>
									<button class="small-btn" onclick={() => (confirmingDelete = null)}>Cancel</button>
								{:else}
									<button class="small-btn danger-outline" onclick={() => (confirmingDelete = model.model_name)}>
										Delete
									</button>
								{/if}
							{:else if downloadingModel === model.model_name}
								<span class="download-status">{downloadProgress}</span>
							{:else}
								<button
									class="small-btn accent"
									onclick={() => handleDownloadModel(model.model_name)}
									disabled={downloadingModel !== null}
								>
									Download
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- Voice Conversion (CosyVoice) -->
		<div class="section">
			<div class="section-title">Voice Conversion</div>
			<div class="card">
				<div class="hint-text" style="margin-bottom: 8px">
					CosyVoice converts your voice directly, preserving natural timing and inflection.
				</div>
				{#each modelStatuses.filter((m) => m.category === 'voice-conversion') as model}
					<div class="model-row">
						<div class="model-info">
							<div class="model-name">{model.display_name}</div>
							<div class="model-status-text">
								{model.downloaded ? 'Downloaded' : 'Not downloaded'}
							</div>
						</div>
						<div class="model-actions">
							{#if model.downloaded}
								{#if confirmingDelete === model.model_name}
									<button
										class="small-btn danger"
										onclick={() => handleDeleteModel(model.model_name)}
										disabled={deletingModel === model.model_name}
									>
										{deletingModel === model.model_name ? 'Deleting...' : 'Confirm'}
									</button>
									<button class="small-btn" onclick={() => (confirmingDelete = null)}>Cancel</button>
								{:else}
									<button class="small-btn danger-outline" onclick={() => (confirmingDelete = model.model_name)}>
										Delete
									</button>
								{/if}
							{:else if downloadingModel === model.model_name}
								<span class="download-status">{downloadProgress}</span>
							{:else}
								<button
									class="small-btn accent"
									onclick={() => handleDownloadModel(model.model_name)}
									disabled={downloadingModel !== null}
								>
									Download
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.models-page {
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
		max-width: 480px;
		margin: 0 auto;
		width: 100%;
	}
	.header h2 {
		font-size: 18px;
		font-weight: 600;
		color: #f1f5f9;
		margin: 0;
	}
	.section {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.section-title {
		font-size: 12px;
		font-weight: 600;
		color: #94a3b8;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.card {
		background: #1e293b;
		border-radius: 8px;
		padding: 12px;
	}
	.hint-text {
		font-size: 11px;
		color: #64748b;
		line-height: 1.4;
	}
	.status.invalid {
		font-size: 12px;
		color: #ef4444;
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
	.download-status {
		font-size: 10px;
		color: #94a3b8;
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>

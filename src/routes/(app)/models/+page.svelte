<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState } from '$lib/state.svelte';
	import { logger } from '$lib/logger';
	import { VoiceboxClient, type VoiceboxModelStatus } from '$lib/voicebox';
	import ModelCard from '$lib/ModelCard.svelte';
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
			logger.error('models', 'Model download failed', err);
		}
		downloadingModel = null;
	}

	async function handleDeleteModel(modelName: string) {
		deletingModel = modelName;
		try {
			await getClient().deleteModel(modelName);
			// Refresh statuses before fallback selection so we use fresh data
			await loadModelStatuses();
			// If we deleted the active whisper model, select another downloaded one
			if (modelName === appState.config.whisper_model) {
				const otherWhisper = modelStatuses.find(
					(m) => m.category === 'transcription' && m.downloaded && m.model_name !== modelName
				);
				appState.config.whisper_model = otherWhisper?.model_name ?? 'whisper-large-v3-turbo';
				await appState.saveConfig();
			}
		} catch (err) {
			modelsError = `Delete failed: ${err}`;
			logger.error('models', 'Model deletion failed', err);
		}
		deletingModel = null;
		confirmingDelete = null;
	}

	async function selectWhisperModel(modelName: string) {
		const prev = appState.config.whisper_model;
		appState.config.whisper_model = modelName;
		try {
			await appState.saveConfig();
		} catch (err) {
			appState.config.whisper_model = prev;
			modelsError = `Failed to save model selection: ${err}`;
			logger.error('models', 'Failed to save whisper model selection', err);
		}
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
					<ModelCard
						{model}
						{downloadingModel}
						{downloadProgress}
						{confirmingDelete}
						{deletingModel}
						activeModelName={appState.config.whisper_model}
						onSelect={selectWhisperModel}
						onDownload={handleDownloadModel}
						onDelete={handleDeleteModel}
						onConfirmDelete={(name) => (confirmingDelete = name)}
						onCancelDelete={() => (confirmingDelete = null)}
					/>
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
					<ModelCard
						{model}
						{downloadingModel}
						{downloadProgress}
						{confirmingDelete}
						{deletingModel}
						onDownload={handleDownloadModel}
						onDelete={handleDeleteModel}
						onConfirmDelete={(name) => (confirmingDelete = name)}
						onCancelDelete={() => (confirmingDelete = null)}
					/>
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
					<ModelCard
						{model}
						{downloadingModel}
						{downloadProgress}
						{confirmingDelete}
						{deletingModel}
						onDownload={handleDownloadModel}
						onDelete={handleDeleteModel}
						onConfirmDelete={(name) => (confirmingDelete = name)}
						onCancelDelete={() => (confirmingDelete = null)}
					/>
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
</style>

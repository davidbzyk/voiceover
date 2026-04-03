<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState, isTauri, type Voice } from '$lib/state.svelte';
	import { tauriInvoke } from '$lib/tauri';
	import { logger } from '$lib/logger';
	import { VoiceboxClient, type VoiceboxModelStatus } from '$lib/voicebox';
	import { onMount } from 'svelte';

	let newVoiceName = $state('');
	let newVoiceId = $state('');
	let apiKeyVisible = $state(false);
	let testingKey = $state(false);
	let keyValid = $state<boolean | null>(null);

	// Local TTS state
	interface LocalVoice {
		id: string;
		name: string;
		language: string;
	}
	let localVoices = $state<LocalVoice[]>([]);
	let localLoading = $state(false);
	let localError = $state('');

	// Model management state
	let modelStatuses = $state<VoiceboxModelStatus[]>([]);
	let modelsLoading = $state(false);
	let modelsError = $state('');
	let downloadingModel = $state<string | null>(null);
	let downloadProgress = $state('');
	let confirmingDelete = $state<string | null>(null);
	let deletingModel = $state<string | null>(null);

	// Derived: are required models ready for current mode?
	let requiredModelsReady = $derived(() => {
		const required = [appState.config.whisper_model];
		if (appState.config.local_tts_mode === 'vc') {
			required.push('cosyvoice3-0.5B');
		} else {
			required.push('qwen-tts-1.7B');
		}
		return required.every((name) =>
			modelStatuses.some((m) => m.model_name === name && m.downloaded)
		);
	});

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
			logger.error('settings', 'Failed to load model statuses', err);
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
		loadLocalVoices();
		if (appState.config.provider === 'local') {
			loadModelStatuses();
		}
	});

	async function loadLocalVoices() {
		localLoading = true;
		localError = '';
		try {
			localVoices = await tauriInvoke<LocalVoice[]>('list_local_voices');
		} catch (err) {
			localError = 'TTS engine unavailable. Try restarting the app.';
			logger.error('settings', 'Failed to load local voices', err);
		}
		localLoading = false;
	}

	async function setProvider(provider: string) {
		appState.config.provider = provider;
		await appState.saveConfig();
		if (provider === 'local') {
			loadLocalVoices();
		}
	}

	async function setLocalVoice(profileId: string) {
		appState.config.local_voice_profile_id = profileId;
		await appState.saveConfig();
	}

	async function setDefaultLocalVoice(profileId: string) {
		appState.config.local_voice_profile_id = profileId;
		await appState.saveConfig();
	}

	async function removeLocalVoice(profileId: string) {
		try {
			await tauriInvoke<string>('sidecar_fetch', {
				path: `/profiles/${profileId}`,
				method: 'DELETE',
				body: null,
			});
			// If we deleted the active voice, clear the selection
			if (appState.config.local_voice_profile_id === profileId) {
				appState.config.local_voice_profile_id = '';
				await appState.saveConfig();
			}
			await loadLocalVoices();
		} catch (err) {
			logger.error('settings', 'Failed to delete voice profile', err);
		}
	}


	let testError = $state('');

	async function testApiKey() {
		testingKey = true;
		keyValid = null;
		testError = '';
		const key = appState.config.elevenlabs_api_key.trim();
		if (!key) {
			keyValid = false;
			testingKey = false;
			return;
		}
		const masked = key.slice(0, 6) + '...' + key.slice(-4);
		logger.elevenLabsTest(masked);
		try {
			if (isTauri()) {
				const { invoke } = await import('@tauri-apps/api/core');
				keyValid = await invoke<boolean>('test_api_key', { apiKey: key });
			} else {
				const resp = await fetch('https://api.elevenlabs.io/v1/user', {
					headers: { 'xi-api-key': key }
				});
				keyValid = resp.ok;
				if (!resp.ok) testError = `HTTP ${resp.status}`;
			}
			logger.elevenLabsTestResult(keyValid ?? false);
		} catch (err) {
			keyValid = false;
			testError = String(err);
		}
		testingKey = false;
	}

	function addVoice() {
		if (!newVoiceName.trim() || !newVoiceId.trim()) return;
		const isFirst = appState.config.voices.length === 0;
		appState.config.voices = [
			...appState.config.voices,
			{
				id: newVoiceId.trim(),
				name: newVoiceName.trim(),
				description: '',
				is_default: isFirst
			}
		];
		newVoiceName = '';
		newVoiceId = '';
		appState.saveConfig();
	}

	function removeVoice(id: string) {
		const wasDefault = appState.config.voices.find((v) => v.id === id)?.is_default;
		appState.config.voices = appState.config.voices.filter((v) => v.id !== id);
		if (wasDefault && appState.config.voices.length > 0) {
			appState.config.voices[0].is_default = true;
		}
		appState.saveConfig();
	}

	function setDefault(id: string) {
		appState.config.voices = appState.config.voices.map((v) => ({
			...v,
			is_default: v.id === id
		}));
		appState.saveConfig();
	}

	let connectingDrive = $state(false);
	let driveError = $state('');

	async function connectDrive() {
		connectingDrive = true;
		driveError = '';
		logger.driveConnect();
		try {
			let tokens: { access_token: string; refresh_token: string; email: string; connected: boolean };
			if (isTauri()) {
				const { invoke } = await import('@tauri-apps/api/core');
				tokens = await invoke('google_drive_connect', {
					clientId: appState.config.google_drive.client_id,
					clientSecret: appState.config.google_drive.client_secret
				});
			} else {
				// Browser mode: OAuth loopback needs Rust TCP listener
				driveError = 'Google Drive connection requires the desktop app. Connect there first, then refresh here.';
				connectingDrive = false;
				return;
			}
			appState.config.google_drive = {
				...appState.config.google_drive,
				...tokens
			};
			await appState.saveConfig();
		} catch (err) {
			driveError = String(err);
		}
		connectingDrive = false;
	}

	async function disconnectDrive() {
		appState.config.google_drive = {
			...appState.config.google_drive,
			access_token: '',
			refresh_token: '',
			email: '',
			connected: false
		};
		await appState.saveConfig();
	}
	let activeTab = $state<'voice' | 'recording' | 'cloud' | 'models'>('voice');

	const tabs: { value: 'voice' | 'recording' | 'cloud' | 'models'; label: string }[] = [
		{ value: 'voice', label: 'Voice' },
		{ value: 'recording', label: 'Recording' },
		{ value: 'cloud', label: 'Cloud' },
		{ value: 'models', label: 'Models' },
	];

	// Load model statuses when switching to models tab
	$effect(() => {
		if (activeTab === 'models') {
			loadModelStatuses();
		}
	});
</script>

<div class="settings">
	<div class="header">
		<h2>Settings</h2>
	</div>

	<div class="tab-bar">
		{#each tabs as tab}
			<button
				class="tab-btn"
				class:active={activeTab === tab.value}
				onclick={() => (activeTab = tab.value)}
			>
				{tab.label}
			</button>
		{/each}
	</div>

	{#if activeTab === 'voice'}
		<!-- TTS Provider Toggle -->
		<div class="section">
			<div class="section-title">TTS Provider</div>
			<div class="card">
				<div class="provider-toggle">
					<button
						class="provider-btn"
						class:active={appState.config.provider === 'elevenlabs'}
						onclick={() => setProvider('elevenlabs')}
					>
						ElevenLabs
					</button>
					<button
						class="provider-btn"
						class:active={appState.config.provider === 'local'}
						onclick={() => setProvider('local')}
					>
						Local
					</button>
				</div>
			</div>
		</div>

		{#if appState.config.provider === 'local'}
			<!-- Local Voice Collection -->
			<div class="section">
				<div class="section-header">
					<div class="section-title">Voice Collection</div>
				</div>
				<div class="card">
					{#if localLoading}
						<div class="hint-text">Loading voices...</div>
					{:else if localError}
						<div class="status invalid">{localError}</div>
					{:else if localVoices.length > 0}
						{#each localVoices as voice}
							<div class="voice-item" class:default={voice.id === appState.config.local_voice_profile_id}>
								<div class="voice-info">
									<div class="voice-name">{voice.name}</div>
									<div class="voice-id">{voice.id.slice(0, 20)}</div>
								</div>
								<div class="voice-actions">
									{#if voice.id === appState.config.local_voice_profile_id}
										<span class="default-badge">Default</span>
									{:else}
										<button class="link-btn" onclick={() => setDefaultLocalVoice(voice.id)}>Set default</button>
									{/if}
									<button class="link-btn danger" onclick={() => removeLocalVoice(voice.id)}>Remove</button>
								</div>
							</div>
						{/each}
					{:else}
						<div class="hint-text">No voice profiles yet. Create one to get started.</div>
					{/if}

					{#if requiredModelsReady()}
						<button class="small-btn accent" onclick={() => goto('/create-voice')}>
							+ Create Voice
						</button>
					{:else}
						<button class="small-btn accent" onclick={() => (activeTab = 'models')}>
							Setup Models
						</button>
					{/if}
				</div>

				<div class="section-header">
					<div class="section-title">Voice Mode</div>
				</div>
				<div class="card">
					<div class="hint-text" style="margin-bottom: 8px">
						<strong>Text-to-Speech:</strong> Transcribes then generates new speech (faster, less sync)<br>
						<strong>Voice Conversion:</strong> Converts your voice directly (slower, preserves timing)
					</div>
					<div class="toggle-row">
						<button
							class="toggle-btn"
							class:active={appState.config.local_tts_mode !== 'vc'}
							onclick={() => { appState.config.local_tts_mode = 'tts'; appState.saveConfig(); }}
						>Text-to-Speech</button>
						<button
							class="toggle-btn"
							class:active={appState.config.local_tts_mode === 'vc'}
							onclick={() => { appState.config.local_tts_mode = 'vc'; appState.saveConfig(); }}
						>Voice Conversion</button>
					</div>
				</div>
			</div>
		{:else}
			<!-- ElevenLabs Voice Collection -->
			<div class="section">
				<div class="section-header">
					<div class="section-title">Voice Collection</div>
				</div>

				<div class="card">
					{#each appState.config.voices as voice}
						<div class="voice-item" class:default={voice.is_default}>
							<div class="voice-info">
								<div class="voice-name">{voice.name}</div>
								<div class="voice-id">{voice.id}</div>
							</div>
							<div class="voice-actions">
								{#if voice.is_default}
									<span class="default-badge">★ Default</span>
								{:else}
									<button class="link-btn" onclick={() => setDefault(voice.id)}>Set default</button>
								{/if}
								<button class="link-btn danger" onclick={() => removeVoice(voice.id)}>Remove</button>
							</div>
						</div>
					{/each}

					<div class="add-voice">
						<input bind:value={newVoiceName} placeholder="Voice name" class="input small" />
						<input bind:value={newVoiceId} placeholder="Voice ID" class="input small" />
						<button
							class="small-btn accent"
							onclick={addVoice}
							disabled={!newVoiceName.trim() || !newVoiceId.trim()}
						>
							+ Add
						</button>
					</div>
				</div>
			</div>
		{/if}

	{:else if activeTab === 'recording'}
		<!-- Output -->
		<div class="section">
			<div class="section-title">Output</div>
			<div class="card">
				<label class="field-label" for="output-dir">Save Location</label>
				<input id="output-dir" bind:value={appState.config.output_dir} class="input" onblur={() => appState.saveConfig()} />
			</div>
		</div>

	{:else if activeTab === 'cloud'}
		<!-- ElevenLabs API Key -->
		<form class="section" onsubmit={(e) => { e.preventDefault(); testApiKey(); }}>
			<div class="section-title">ElevenLabs API Key</div>
			<div class="card">
				<label class="field-label" for="api-key">API Key</label>
				<div class="key-row">
					<input
						id="api-key"
						type={apiKeyVisible ? 'text' : 'password'}
						bind:value={appState.config.elevenlabs_api_key}
						placeholder="sk-..."
						class="input"
						autocomplete="off"
						onblur={() => appState.saveConfig()}
					/>
					<button class="small-btn" onclick={() => (apiKeyVisible = !apiKeyVisible)}>
						{apiKeyVisible ? '🙈' : '👁️'}
					</button>
					<button class="small-btn" onclick={testApiKey} disabled={testingKey}>
						{testingKey ? '...' : 'Test'}
					</button>
				</div>
				{#if keyValid === true}
					<div class="status valid">✓ Valid API key</div>
				{:else if keyValid === false}
					<div class="status invalid">✕ Invalid API key{testError ? `: ${testError}` : ''}</div>
				{/if}
			</div>
		</form>

		<!-- Google Drive -->
		<div class="section">
			<div class="section-title">Google Drive</div>
			<div class="card">
				{#if appState.config.google_drive.connected}
					<div class="drive-status">
						<div class="drive-connected">
							<span class="drive-dot"></span>
							Connected as {appState.config.google_drive.email || 'unknown'}
						</div>
						<button class="link-btn danger" onclick={disconnectDrive}>Disconnect</button>
					</div>
				{:else}
					<label class="field-label" for="gdrive-client-id">OAuth Client ID</label>
					<input
						id="gdrive-client-id"
						bind:value={appState.config.google_drive.client_id}
						placeholder="your-app.apps.googleusercontent.com"
						class="input"
						onblur={() => appState.saveConfig()}
					/>
					<label class="field-label" for="gdrive-client-secret">Client Secret</label>
					<input
						id="gdrive-client-secret"
						type="password"
						bind:value={appState.config.google_drive.client_secret}
						placeholder="GOCSPX-..."
						class="input"
						autocomplete="off"
						onblur={() => appState.saveConfig()}
					/>
					<div class="drive-hint">
						Create at console.cloud.google.com → APIs → Credentials → OAuth 2.0 Client ID (Desktop app)
					</div>
					<button
						class="small-btn accent"
						onclick={connectDrive}
						disabled={!appState.config.google_drive.client_id.trim() || !appState.config.google_drive.client_secret.trim() || connectingDrive}
					>
						{connectingDrive ? 'Connecting...' : 'Connect Google Drive'}
					</button>
					{#if driveError}
						<div class="status invalid">{driveError}</div>
					{/if}
				{/if}
			</div>
		</div>
	{:else if activeTab === 'models'}
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
	{/if}
</div>

<style>
	.settings {
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
		max-width: 480px;
		margin: 0 auto;
		width: 100%;
	}
	.tab-bar {
		display: flex;
		gap: 4px;
		background: #0f172a;
		border-radius: 6px;
		padding: 3px;
	}
	.tab-btn {
		flex: 1;
		background: transparent;
		border: none;
		color: #64748b;
		padding: 8px 12px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 13px;
		font-weight: 500;
		transition: all 0.15s;
	}
	.tab-btn.active {
		background: #334155;
		color: #f1f5f9;
	}
	.tab-btn:hover:not(.active) {
		color: #94a3b8;
	}
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.input.small {
		flex: 1;
	}
	.key-row {
		display: flex;
		gap: 6px;
	}
	.voice-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 10px 0;
		border-bottom: 1px solid #334155;
	}
	.voice-item:last-of-type {
		border-bottom: none;
	}
	.voice-item.default {
		background: rgba(249, 115, 22, 0.05);
		border-radius: 6px;
		padding: 10px;
		margin: -4px -4px;
	}
	.voice-name {
		font-size: 13px;
	}
	.voice-id {
		font-size: 10px;
		color: #64748b;
		font-family: monospace;
	}
	.voice-actions {
		display: flex;
		gap: 8px;
		align-items: center;
	}
	.default-badge {
		font-size: 10px;
		color: #f97316;
	}
	.link-btn {
		background: none;
		border: none;
		color: #64748b;
		font-size: 10px;
		cursor: pointer;
	}
	.link-btn:hover {
		color: #94a3b8;
	}
	.link-btn.danger:hover {
		color: #ef4444;
	}
	.add-voice {
		display: flex;
		gap: 6px;
		padding-top: 8px;
		border-top: 1px solid #334155;
	}
	.drive-status {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.drive-connected {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
		color: #cbd5e1;
	}
	.drive-dot {
		width: 8px;
		height: 8px;
		background: #22c55e;
		border-radius: 50%;
	}
	.drive-hint {
		font-size: 10px;
		color: #64748b;
		line-height: 1.4;
	}
	.toggle-row {
		display: flex;
		gap: 8px;
	}
	.toggle-btn {
		flex: 1;
		padding: 8px 12px;
		border: 1px solid #334155;
		border-radius: 6px;
		background: transparent;
		color: #94a3b8;
		font-size: 12px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.toggle-btn.active {
		background: #1e293b;
		border-color: #6366f1;
		color: #e2e8f0;
	}
	/* Model management styles */
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

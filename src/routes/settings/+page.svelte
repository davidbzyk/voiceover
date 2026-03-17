<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState, isTauri, type Voice } from '$lib/state.svelte';
	import { logger } from '$lib/logger';

	let newVoiceName = $state('');
	let newVoiceId = $state('');
	let apiKeyVisible = $state(false);
	let testingKey = $state(false);
	let keyValid = $state<boolean | null>(null);

	async function saveAndBack() {
		await appState.saveConfig();
		goto('/');
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
	}

	function removeVoice(id: string) {
		const wasDefault = appState.config.voices.find((v) => v.id === id)?.is_default;
		appState.config.voices = appState.config.voices.filter((v) => v.id !== id);
		if (wasDefault && appState.config.voices.length > 0) {
			appState.config.voices[0].is_default = true;
		}
	}

	function setDefault(id: string) {
		appState.config.voices = appState.config.voices.map((v) => ({
			...v,
			is_default: v.id === id
		}));
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
</script>

<div class="settings">
	<div class="header">
		<button class="back-btn" onclick={saveAndBack}>← Back</button>
		<h2>Settings</h2>
	</div>

	<!-- ElevenLabs API Key -->
	<form class="section" onsubmit={(e) => { e.preventDefault(); testApiKey(); }}>
		<div class="section-title">ElevenLabs</div>
		<div class="card">
			<label class="field-label">API Key</label>
			<div class="key-row">
				<input
					type={apiKeyVisible ? 'text' : 'password'}
					bind:value={appState.config.elevenlabs_api_key}
					placeholder="sk-..."
					class="input"
					autocomplete="off"
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

	<!-- Voice Collection -->
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

	<!-- Output -->
	<div class="section">
		<div class="section-title">Output</div>
		<div class="card">
			<label class="field-label">Save Location</label>
			<input bind:value={appState.config.output_dir} class="input" />
		</div>
	</div>

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
				<label class="field-label">OAuth Client ID</label>
				<input
					bind:value={appState.config.google_drive.client_id}
					placeholder="your-app.apps.googleusercontent.com"
					class="input"
				/>
				<label class="field-label">Client Secret</label>
				<input
					type="password"
					bind:value={appState.config.google_drive.client_secret}
					placeholder="GOCSPX-..."
					class="input"
					autocomplete="off"
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
</div>

<style>
	.settings {
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
		max-width: 480px;
	}
	.header {
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.header h2 {
		margin: 0;
		font-size: 18px;
	}
	.back-btn {
		background: #334155;
		border: none;
		color: #94a3b8;
		padding: 6px 12px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 13px;
	}
	.back-btn:hover {
		background: #475569;
		color: #f1f5f9;
	}
	.section {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.section-title {
		font-size: 13px;
		font-weight: 600;
	}
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.card {
		background: #1e293b;
		border-radius: 8px;
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.field-label {
		font-size: 11px;
		color: #64748b;
	}
	.input {
		background: #0f172a;
		border: 1px solid #334155;
		border-radius: 6px;
		padding: 8px 12px;
		color: #cbd5e1;
		font-size: 12px;
		outline: none;
		width: 100%;
	}
	.input.small {
		flex: 1;
	}
	.input:focus {
		border-color: #f97316;
	}
	.key-row {
		display: flex;
		gap: 6px;
	}
	.small-btn {
		background: #334155;
		border: none;
		color: #94a3b8;
		padding: 6px 10px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 12px;
		white-space: nowrap;
	}
	.small-btn:hover {
		background: #475569;
	}
	.small-btn.accent {
		background: #f97316;
		color: white;
	}
	.small-btn.accent:disabled {
		opacity: 0.4;
	}
	.status {
		font-size: 11px;
	}
	.status.valid {
		color: #22c55e;
	}
	.status.invalid {
		color: #ef4444;
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
</style>

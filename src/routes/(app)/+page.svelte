<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState, isTauri } from '$lib/state.svelte';
	import {
		startRecording,
		stopRecording,
		pauseRecording,
		resumeRecording,
		cancelRecording,
		getAudioDevices,
		confirmRegionSelection,
		cancelRegionSelection,
		type CaptureMode
	} from '$lib/recorder.svelte';
	import { onMount, onDestroy } from 'svelte';
	import { logger } from '$lib/logger';
	import { tauriInvoke } from '$lib/tauri';
	import type { VoiceboxProfile } from '$lib/voicebox';
	import WebcamBubble from '$lib/WebcamBubble.svelte';
	import RegionSelector from '$lib/RegionSelector.svelte';

	let captureMode = $state<CaptureMode>('fullscreen');
	let audioDevices = $state<MediaDeviceInfo[]>([]);
	let selectedDeviceId = $state<string>('');
	let isStarting = $state(false);
	let pausedAt = $state(0);
	let totalPausedMs = $state(0);
	let timerHandle = $state<ReturnType<typeof setInterval> | null>(null);

	// Local voice profiles
	let localVoices = $state<VoiceboxProfile[]>([]);

	async function loadLocalVoicesIfNeeded() {
		if (appState.config.provider === 'local' && isTauri() && localVoices.length === 0) {
			try {
				localVoices = await tauriInvoke<VoiceboxProfile[]>('list_local_voices');
			} catch {
				// Sidecar might not be ready yet
			}
		}
	}

	onMount(async () => {
		// If there's a pending recording, redirect to preview
		if (appState.recordingPath && ['recorded', 'processing', 'complete', 'saved'].includes(appState.recordingState)) {
			goto('/preview');
			return;
		}

		try {
			audioDevices = await getAudioDevices();
			if (audioDevices.length > 0) {
				selectedDeviceId = audioDevices[0].deviceId;
			}
		} catch (err) {
			logger.debug('audio', 'Could not enumerate devices at mount', err);
		}

		// Config may not be loaded yet at mount — load voices after a short delay
		await loadLocalVoicesIfNeeded();
		// Retry after config has had time to load from Tauri
		setTimeout(loadLocalVoicesIfNeeded, 1500);
	});

	onDestroy(() => {
		if (timerHandle) { clearInterval(timerHandle); timerHandle = null; }
	});

	async function handleRecord() {
		if (isStarting) return;
		isStarting = true;

		try {
			appState.recordingState = 'selecting';

			await startRecording(
				captureMode,
				selectedDeviceId || undefined,
				appState.config.preferences.webcam_enabled
			);

			appState.recordingState = 'recording';
			pausedAt = 0;
			totalPausedMs = 0;

			// Start duration timer (subtracts paused time from elapsed)
			if (timerHandle) { clearInterval(timerHandle); timerHandle = null; }
			const startTime = Date.now();
			timerHandle = setInterval(() => {
				if (appState.recordingState === 'recording') {
					appState.recordingDuration = Math.floor((Date.now() - startTime - totalPausedMs) / 1000);
				} else if (appState.recordingState !== 'paused') {
					if (timerHandle) { clearInterval(timerHandle); timerHandle = null; }
				}
			}, 1000);
		} catch (err) {
			appState.recordingState = 'ready';
			appState.errorMessage = err instanceof Error ? err.message : String(err);
		} finally {
			isStarting = false;
		}
	}

	async function handleStop() {
		if (timerHandle) { clearInterval(timerHandle); timerHandle = null; }
		try {
			const path = await stopRecording();
			appState.recordingPath = path;
			appState.recordingState = 'recorded';
			goto('/preview');
		} catch (err) {
			appState.errorMessage = err instanceof Error ? err.message : String(err);
			appState.recordingState = 'ready';
		}
	}

	function handleCancel() {
		if (timerHandle) { clearInterval(timerHandle); timerHandle = null; }
		cancelRecording();
		appState.reset();
	}

	function handlePause() {
		if (appState.recordingState === 'recording') {
			pauseRecording();
			pausedAt = Date.now();
			appState.recordingState = 'paused';
		} else if (appState.recordingState === 'paused') {
			totalPausedMs += Date.now() - pausedAt;
			pausedAt = 0;
			resumeRecording();
			appState.recordingState = 'recording';
		}
	}

	function formatTime(seconds: number): string {
		const m = Math.floor(seconds / 60).toString().padStart(2, '0');
		const s = (seconds % 60).toString().padStart(2, '0');
		return `${m}:${s}`;
	}

	const isRecording = $derived(
		appState.recordingState === 'recording' || appState.recordingState === 'paused'
	);
	const isSelecting = $derived(
		appState.recordingState === 'selecting' || appState.recordingState === 'selecting-region'
	);

	const captureModes: { value: CaptureMode; label: string; icon: string }[] = [
		{ value: 'fullscreen', label: 'Full Screen', icon: '🖥️' },
		{ value: 'window', label: 'Window', icon: '🪟' },
		{ value: 'region', label: 'Region', icon: '⬜' }
	];
</script>

<div class="home">
	<!-- Capture mode -->
	<div class="section">
		<div class="section-label">Capture Mode</div>
		<div class="mode-selector">
			{#each captureModes as mode}
				<button
					class="mode-btn"
					class:active={captureMode === mode.value}
					onclick={() => (captureMode = mode.value)}
				>
					{mode.icon} {mode.label}
				</button>
			{/each}
		</div>
	</div>

	<!-- Options row -->
	<div class="section">
		<div class="options-row">
			<!-- Mic selector -->
			<div class="option-card">
				<span class="option-icon">🎤</span>
				<select bind:value={selectedDeviceId} class="option-select">
					{#each audioDevices as device}
						<option value={device.deviceId}>{device.label || 'Microphone'}</option>
					{/each}
					{#if audioDevices.length === 0}
						<option value="">System Default</option>
					{/if}
				</select>
			</div>

			<!-- Webcam toggle -->
			<button
				class="option-card clickable"
				onclick={() =>
					(appState.config.preferences.webcam_enabled =
						!appState.config.preferences.webcam_enabled)}
			>
				<span class="option-icon">📷</span>
				<span>
					Webcam:
					<span class={appState.config.preferences.webcam_enabled ? 'on' : 'off'}>
						{appState.config.preferences.webcam_enabled ? 'ON' : 'OFF'}
					</span>
				</span>
			</button>

		</div>
	</div>

	<!-- Voice replacement toggle -->
	<div class="section">
		<div class="toggle-row">
			<div>
				<div class="toggle-label">🎙️ Voice Replacement</div>
				<div class="toggle-hint">
					{#if !appState.config.preferences.voice_replacement_enabled}
						Disabled — raw recording only
					{:else if appState.config.provider === 'local'}
						Local: {localVoices.find(v => v.id === appState.config.local_voice_profile_id)?.name ?? 'None selected'}
					{:else}
						ElevenLabs: {appState.selectedVoice?.name ?? 'None'}
					{/if}
				</div>
			</div>
			<button
				class="toggle"
				class:active={appState.config.preferences.voice_replacement_enabled}
				aria-label="Toggle voice replacement"
				onclick={() =>
					(appState.config.preferences.voice_replacement_enabled =
						!appState.config.preferences.voice_replacement_enabled)}
			>
				<div class="toggle-knob"></div>
			</button>
		</div>

		{#if appState.config.preferences.voice_replacement_enabled}
			<!-- Provider toggle -->
			<div class="provider-toggle">
				<button
					class="provider-btn"
					class:active={appState.config.provider === 'elevenlabs'}
					onclick={() => { appState.config.provider = 'elevenlabs'; appState.saveConfig(); }}
				>
					ElevenLabs
				</button>
				<button
					class="provider-btn"
					class:active={appState.config.provider === 'local'}
					onclick={async () => {
						appState.config.provider = 'local';
						appState.saveConfig();
						if (isTauri()) {
							try { localVoices = await tauriInvoke<VoiceboxProfile[]>('list_local_voices'); } catch {}
						}
					}}
				>
					Local
				</button>
			</div>

			{#if appState.config.provider === 'local'}
				<!-- Voice mode toggle (TTS vs VC) -->
				<div class="voice-mode-toggle">
					<button
						class="voice-mode-btn"
						class:active={appState.config.local_tts_mode !== 'vc'}
						onclick={() => { appState.config.local_tts_mode = 'tts'; appState.saveConfig(); }}
					>Text-to-Speech</button>
					<button
						class="voice-mode-btn"
						class:active={appState.config.local_tts_mode === 'vc'}
						onclick={() => { appState.config.local_tts_mode = 'vc'; appState.saveConfig(); }}
					>Voice Conversion</button>
				</div>
			{/if}

			<!-- Voice selector based on provider -->
			{#if appState.config.provider === 'elevenlabs'}
				<div class="option-card">
					<span class="option-icon">🎙️</span>
					{#if appState.config.voices.length > 0}
						<select
							class="option-select"
							value={appState.selectedVoice?.id ?? ''}
							onchange={(e) => {
								const target = e.target as HTMLSelectElement;
								appState.config.voices = appState.config.voices.map((v) => ({
									...v,
									is_default: v.id === target.value
								}));
								appState.saveConfig();
							}}
						>
							{#each appState.config.voices as voice}
								<option value={voice.id}>{voice.name}</option>
							{/each}
						</select>
					{:else}
						<span class="option-hint">No voices — add in Settings</span>
					{/if}
				</div>
			{:else}
				<div class="option-card">
					<span class="option-icon">🎙️</span>
					{#if localVoices.length > 0}
						<select
							class="option-select"
							value={appState.config.local_voice_profile_id}
							onchange={(e) => {
								appState.config.local_voice_profile_id = (e.target as HTMLSelectElement).value;
								appState.saveConfig();
							}}
						>
							<option value="">Select a voice...</option>
							{#each localVoices as voice}
								<option value={voice.id}>{voice.name} ({voice.language})</option>
							{/each}
						</select>
					{:else}
						<span class="option-hint">No local voices — create in Settings</span>
					{/if}
				</div>
			{/if}
		{/if}
	</div>

	<!-- Record / Stop controls -->
	<div class="record-area">
		{#if isRecording}
			<!-- Recording in progress -->
			<div class="recording-indicator">
				<div class="rec-dot" class:paused={appState.recordingState === 'paused'}></div>
				<span class="rec-time">{formatTime(appState.recordingDuration)}</span>
				<span class="rec-label">
					{appState.recordingState === 'paused' ? 'Paused' : 'Recording'}
				</span>
			</div>
			<div class="recording-controls">
				<button class="ctrl-btn" onclick={handlePause} aria-label={appState.recordingState === 'paused' ? 'Resume' : 'Pause'}>
					{appState.recordingState === 'paused' ? '▶' : '⏸'}
				</button>
				<button class="ctrl-btn stop" onclick={handleStop} aria-label="Stop">⏹</button>
				<button class="ctrl-btn cancel" onclick={handleCancel} aria-label="Cancel">✕</button>
			</div>
		{:else if isSelecting}
			<!-- Waiting for screen share permission -->
			<div class="record-btn starting" aria-label="Waiting for screen selection">
				<div class="record-dot"></div>
			</div>
			<div class="record-hint">Select a screen to share...</div>
			<button class="ctrl-btn cancel" onclick={handleCancel} aria-label="Cancel">✕</button>
		{:else}
			<!-- Ready to record -->
			<button
				class="record-btn"
				onclick={handleRecord}
				disabled={isStarting || !appState.ffmpegAvailable}
				aria-label="Start recording"
			>
				<div class="record-dot"></div>
			</button>
			<div class="record-hint">
				{#if isStarting}
					Starting...
				{:else}
					Click to record
				{/if}
			</div>
		{/if}
	</div>

	<!-- Error message -->
	{#if appState.errorMessage}
		<div class="error-msg">
			{appState.errorMessage}
			<button class="dismiss" onclick={() => (appState.errorMessage = '')}>✕</button>
		</div>
	{/if}

	<WebcamBubble />

	{#if appState.recordingState === 'selecting-region'}
		<RegionSelector
			screenshotUrl={appState.regionScreenshot}
			onSelect={(rect) => confirmRegionSelection(rect)}
			onCancel={() => cancelRegionSelection()}
		/>
	{/if}
</div>

<style>
	.home {
		flex: 1;
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
		max-width: 500px;
		margin: 0 auto;
		width: 100%;
	}

	.section {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.section-label {
		color: #64748b;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 1px;
	}

	.mode-selector {
		display: flex;
		gap: 8px;
	}
	.mode-btn {
		flex: 1;
		background: #334155;
		border: none;
		color: #94a3b8;
		padding: 10px;
		border-radius: 8px;
		font-size: 13px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.mode-btn.active {
		background: #1e40af;
		color: white;
	}
	.mode-btn:hover:not(.active) {
		background: #475569;
	}

	.options-row {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.option-card {
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 8px;
		padding: 10px 14px;
		font-size: 12px;
		color: #cbd5e1;
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.option-card.clickable {
		cursor: pointer;
	}
	.option-card.clickable:hover {
		border-color: #475569;
	}
	.option-icon {
		font-size: 14px;
	}
	.option-select {
		background: transparent;
		border: none;
		color: #cbd5e1;
		font-size: 12px;
		flex: 1;
		outline: none;
	}
	.option-hint {
		color: #64748b;
		font-style: italic;
	}
	.voice-mode-toggle {
		display: flex;
		gap: 8px;
	}
	.voice-mode-btn {
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
	.voice-mode-btn.active {
		background: #1e293b;
		border-color: #6366f1;
		color: #e2e8f0;
	}
	.on {
		color: #22c55e;
	}
	.off {
		color: #64748b;
	}

	.toggle-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		background: #1e293b;
		border-radius: 10px;
		padding: 14px 18px;
	}
	.toggle-label {
		font-size: 14px;
		font-weight: 600;
	}
	.toggle-hint {
		font-size: 11px;
		color: #64748b;
		margin-top: 2px;
	}
	.toggle {
		width: 44px;
		height: 24px;
		background: #334155;
		border: none;
		border-radius: 12px;
		position: relative;
		cursor: pointer;
		transition: background 0.2s;
	}
	.toggle.active {
		background: #f97316;
	}
	.toggle-knob {
		width: 20px;
		height: 20px;
		background: white;
		border-radius: 50%;
		position: absolute;
		top: 2px;
		left: 2px;
		transition: left 0.2s;
	}
	.toggle.active .toggle-knob {
		left: 22px;
	}

	.provider-toggle {
		display: flex;
		gap: 4px;
		background: #0f172a;
		border-radius: 6px;
		padding: 3px;
	}
	.provider-btn {
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
	.provider-btn.active {
		background: #334155;
		color: #f1f5f9;
	}
	.provider-btn:hover:not(.active) {
		color: #94a3b8;
	}

	.record-area {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		padding: 24px 0;
	}
	.record-btn {
		width: 80px;
		height: 80px;
		background: #dc2626;
		border: 4px solid #fca5a5;
		border-radius: 50%;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}
	.record-btn:hover:not(:disabled) {
		transform: scale(1.05);
		background: #ef4444;
	}
	.record-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.record-btn.starting {
		opacity: 0.6;
		animation: pulse 1.5s infinite;
	}
	.record-dot {
		width: 28px;
		height: 28px;
		background: white;
		border-radius: 50%;
	}
	.record-hint {
		color: #64748b;
		font-size: 12px;
	}

	.recording-indicator {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 16px;
	}
	.rec-dot {
		width: 12px;
		height: 12px;
		background: #dc2626;
		border-radius: 50%;
		animation: pulse 1.5s infinite;
	}
	.rec-dot.paused {
		background: #f59e0b;
		animation: none;
	}
	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.3; }
	}
	.rec-time {
		font-size: 28px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.rec-label {
		font-size: 13px;
		color: #64748b;
	}
	.recording-controls {
		display: flex;
		gap: 10px;
	}
	.ctrl-btn {
		width: 48px;
		height: 48px;
		background: #334155;
		border: none;
		border-radius: 12px;
		color: #f1f5f9;
		font-size: 20px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.ctrl-btn:hover {
		background: #475569;
	}
	.ctrl-btn.stop {
		background: #dc2626;
	}
	.ctrl-btn.stop:hover {
		background: #ef4444;
	}
	.ctrl-btn.cancel {
		color: #64748b;
	}

	.error-msg {
		background: #7f1d1d;
		color: #fecaca;
		padding: 10px 14px;
		border-radius: 8px;
		font-size: 12px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.dismiss {
		background: none;
		border: none;
		color: #fecaca;
		cursor: pointer;
		font-size: 14px;
	}
</style>

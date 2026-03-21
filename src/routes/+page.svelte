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
		type CaptureMode
	} from '$lib/recorder.svelte';
	import { onMount } from 'svelte';

	let captureMode = $state<CaptureMode>('fullscreen');
	let audioDevices = $state<MediaDeviceInfo[]>([]);
	let selectedDeviceId = $state<string>('');
	let isStarting = $state(false);

	onMount(async () => {
		try {
			audioDevices = await getAudioDevices();
			if (audioDevices.length > 0) {
				selectedDeviceId = audioDevices[0].deviceId;
			}
		} catch {
			// Permission not yet granted — will prompt on record
		}
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

			// Start duration timer
			const startTime = Date.now();
			const timer = setInterval(() => {
				if (appState.recordingState === 'recording') {
					appState.recordingDuration = Math.floor((Date.now() - startTime) / 1000);
				} else if (
					appState.recordingState !== 'paused' &&
					appState.recordingState !== 'recording'
				) {
					clearInterval(timer);
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
		cancelRecording();
		appState.reset();
	}

	function handlePause() {
		if (appState.recordingState === 'recording') {
			pauseRecording();
			appState.recordingState = 'paused';
		} else if (appState.recordingState === 'paused') {
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

	const captureModes: { value: CaptureMode; label: string; icon: string }[] = [
		{ value: 'fullscreen', label: 'Full Screen', icon: '🖥️' },
		{ value: 'window', label: 'Window', icon: '🪟' },
		{ value: 'region', label: 'Region', icon: '⬜' }
	];
</script>

<div class="home">
	<!-- Top bar -->
	<div class="topbar">
		<div class="logo">🎙️ VoiceOver</div>
		<div class="topbar-actions">
			<button class="topbar-btn" onclick={() => goto('/settings')}>⚙️ Settings</button>
		</div>
	</div>

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

			<!-- Voice selector -->
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
		</div>
	</div>

	<!-- Voice replacement toggle -->
	<div class="section">
		<div class="toggle-row">
			<div>
				<div class="toggle-label">🎙️ Voice Replacement</div>
				<div class="toggle-hint">
					{appState.config.preferences.voice_replacement_enabled
						? `Using: ${appState.selectedVoice?.name ?? 'None'}`
						: 'Disabled — raw recording only'}
				</div>
			</div>
			<button
				class="toggle"
				class:active={appState.config.preferences.voice_replacement_enabled}
				onclick={() =>
					(appState.config.preferences.voice_replacement_enabled =
						!appState.config.preferences.voice_replacement_enabled)}
			>
				<div class="toggle-knob"></div>
			</button>
		</div>
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
</div>

<style>
	.home {
		flex: 1;
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.topbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.logo {
		font-size: 18px;
		font-weight: 700;
		color: #f97316;
	}
	.topbar-actions {
		display: flex;
		gap: 8px;
	}
	.topbar-btn {
		background: #334155;
		border: none;
		color: #94a3b8;
		padding: 6px 14px;
		border-radius: 6px;
		font-size: 12px;
		cursor: pointer;
	}
	.topbar-btn:hover {
		background: #475569;
		color: #f1f5f9;
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

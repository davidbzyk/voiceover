<script lang="ts">
	import { listen } from '@tauri-apps/api/event';
	import { invoke } from '@tauri-apps/api/core';
	import { onMount } from 'svelte';

	let duration = $state(0);
	let isPaused = $state(false);
	let voiceName = $state('');
	let timer: ReturnType<typeof setInterval> | null = null;

	onMount(() => {
		timer = setInterval(() => {
			if (!isPaused) duration++;
		}, 1000);

		// Listen for voice name from main window
		const unlisten = listen<string>('widget-voice-name', (event) => {
			voiceName = event.payload;
		});

		return () => {
			if (timer) clearInterval(timer);
			unlisten.then((fn) => fn());
		};
	});

	function formatTime(seconds: number): string {
		const m = Math.floor(seconds / 60)
			.toString()
			.padStart(2, '0');
		const s = (seconds % 60).toString().padStart(2, '0');
		return `${m}:${s}`;
	}

	function handlePause() {
		isPaused = !isPaused;
		// Notify main window
		invoke('plugin:event|emit', { event: isPaused ? 'recording-pause' : 'recording-resume', payload: null }).catch(() => {});
	}

	async function handleStop() {
		if (timer) clearInterval(timer);
		// Notify main window to stop recording
		const { emit } = await import('@tauri-apps/api/event');
		await emit('recording-stop');
		await invoke('close_widget_window');
	}

	async function handleCancel() {
		if (timer) clearInterval(timer);
		const { emit } = await import('@tauri-apps/api/event');
		await emit('recording-cancel');
		await invoke('close_widget_window');
	}
</script>

<div class="widget">
	<!-- Recording indicator + timer -->
	<div class="info">
		<div class="indicator">
			<div class="dot" class:paused={isPaused}></div>
			<span class="time">{formatTime(duration)}</span>
		</div>
		<div class="meta">
			{isPaused ? 'Paused' : 'Recording'}{voiceName ? ` · ${voiceName}` : ''}
		</div>
	</div>

	<!-- Controls -->
	<div class="controls">
		<button class="ctrl-btn" onclick={handlePause} title={isPaused ? 'Resume' : 'Pause'}>
			{isPaused ? '▶' : '⏸'}
		</button>
		<button class="ctrl-btn stop" onclick={handleStop} title="Stop">⏹</button>
		<button class="ctrl-btn cancel" onclick={handleCancel} title="Cancel">✕</button>
	</div>
</div>

<style>
	:global(body) {
		margin: 0;
		padding: 0;
		background: transparent;
		overflow: hidden;
	}
	.widget {
		display: flex;
		align-items: center;
		gap: 16px;
		background: #1e293b;
		border-radius: 16px;
		padding: 10px 18px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
		border: 1px solid #334155;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
		color: #f1f5f9;
		-webkit-app-region: drag;
	}
	.info {
		flex: 1;
	}
	.indicator {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.dot {
		width: 8px;
		height: 8px;
		background: #dc2626;
		border-radius: 50%;
		animation: pulse 1.5s infinite;
	}
	.dot.paused {
		background: #f59e0b;
		animation: none;
	}
	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.3;
		}
	}
	.time {
		font-size: 18px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.meta {
		font-size: 10px;
		color: #64748b;
		margin-top: 1px;
	}
	.controls {
		display: flex;
		gap: 6px;
		-webkit-app-region: no-drag;
	}
	.ctrl-btn {
		width: 32px;
		height: 32px;
		background: #334155;
		border: none;
		border-radius: 8px;
		color: #f1f5f9;
		font-size: 14px;
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
</style>

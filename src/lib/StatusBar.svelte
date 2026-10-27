<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { appState, isTauri } from '$lib/state.svelte';
	import { tauriInvoke } from '$lib/tauri';
	import { logger } from '$lib/logger';
	import { shouldLoadLocalVoices } from '$lib/conversion';
	import { savedVoiceChoice } from '$lib/conversion';
	import { describeChoice, localVoices } from '$lib/localVoice.svelte';

	let sidecarHealthy = $state(false);
	let pollHandle: ReturnType<typeof setInterval> | null = null;

	async function checkSidecar() {
		if (!isTauri()) return;
		try {
			const status = await tauriInvoke<{ running: boolean; healthy: boolean }>('get_sidecar_status');
			sidecarHealthy = status.healthy;
		} catch (err) {
			sidecarHealthy = false;
			logger.debug('statusbar', 'Sidecar health check failed', err);
		}
	}

	// The config usually loads after the bar mounts, so this runs again once it says the voice is local.
	$effect(() => {
		if (isTauri() && shouldLoadLocalVoices(appState.config) && !localVoices.loaded) localVoices.refresh();
	});

	onMount(() => {
		checkSidecar();
		pollHandle = setInterval(checkSidecar, 30_000);
	});

	onDestroy(() => {
		if (pollHandle) clearInterval(pollHandle);
	});

	const voiceLabel = $derived(
		describeChoice(savedVoiceChoice(appState.config), appState.config, localVoices.profiles, localVoices.engines)
	);
</script>

<div class="status-bar">
	<div class="status-left">
		<span class="status-dot" class:healthy={sidecarHealthy}></span>
		<span class="status-text">TTS {sidecarHealthy ? 'Ready' : 'Offline'}</span>
	</div>
	<div class="status-center">
		<span class="status-text">{voiceLabel}</span>
	</div>
	<div class="status-right">
		<span class="status-text output-dir" title={appState.config.output_dir}>
			{appState.config.output_dir}
		</span>
	</div>
</div>

<style>
	.status-bar {
		height: 28px;
		background: #0f172a;
		border-top: 1px solid #1e293b;
		display: flex;
		align-items: center;
		padding: 0 16px;
		gap: 16px;
		flex-shrink: 0;
	}
	.status-left {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.status-center {
		flex: 1;
		text-align: center;
	}
	.status-right {
		max-width: 200px;
		overflow: hidden;
	}
	.status-text {
		font-size: 11px;
		color: #64748b;
	}
	.output-dir {
		text-overflow: ellipsis;
		overflow: hidden;
		white-space: nowrap;
		display: block;
		direction: rtl;
		text-align: right;
	}
	.status-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: #ef4444;
		flex-shrink: 0;
	}
	.status-dot.healthy {
		background: #22c55e;
	}
</style>

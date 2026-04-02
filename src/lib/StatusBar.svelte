<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { appState, isTauri } from '$lib/state.svelte';
	import { tauriInvoke } from '$lib/tauri';

	let sidecarHealthy = $state(false);
	let pollHandle: ReturnType<typeof setInterval> | null = null;

	async function checkSidecar() {
		if (!isTauri()) return;
		try {
			const status = await tauriInvoke<{ running: boolean; healthy: boolean }>('get_sidecar_status');
			sidecarHealthy = status.healthy;
		} catch {
			sidecarHealthy = false;
		}
	}

	onMount(() => {
		checkSidecar();
		pollHandle = setInterval(checkSidecar, 30_000);
	});

	onDestroy(() => {
		if (pollHandle) clearInterval(pollHandle);
	});

	const providerLabel = $derived(
		appState.config.provider === 'local' ? 'Local TTS' : 'ElevenLabs'
	);

	const voiceLabel = $derived(() => {
		if (appState.config.provider === 'local') {
			return appState.config.local_voice_profile_id || 'No profile';
		}
		const voice = appState.config.voices?.find((v: { is_default: boolean }) => v.is_default)
			?? appState.config.voices?.[0];
		return voice?.name || 'No voice';
	});
</script>

<div class="status-bar">
	<div class="status-left">
		<span class="status-dot" class:healthy={sidecarHealthy}></span>
		<span class="status-text">TTS {sidecarHealthy ? 'Ready' : 'Offline'}</span>
	</div>
	<div class="status-center">
		<span class="status-text">{providerLabel} · {voiceLabel()}</span>
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

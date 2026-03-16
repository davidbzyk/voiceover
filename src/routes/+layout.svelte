<script lang="ts">
	import { onMount } from 'svelte';
	import { appState } from '$lib/state.svelte';
	import '../app.css';

	const isTauri = typeof window !== 'undefined' && !!(window as any).__TAURI_INTERNALS__;

	let { children } = $props();

	onMount(async () => {
		// Always load config (works in both Tauri and browser via localStorage)
		await appState.loadConfig();

		// Tauri-only: check ffmpeg
		if (isTauri) {
			try {
				const { invoke } = await import('@tauri-apps/api/core');
				const status = await invoke<{ ffmpeg_available: boolean }>('check_prerequisites');
				appState.ffmpegAvailable = status.ffmpeg_available;
			} catch (err) {
				console.error('Failed to check prerequisites:', err);
			}
		}
	});
</script>

<main>
	{#if !appState.ffmpegAvailable}
		<div class="error-banner">
			<strong>ffmpeg not found.</strong> Install it:
			<code>brew install ffmpeg</code> (macOS) or <code>sudo apt install ffmpeg</code> (Linux)
		</div>
	{/if}
	{@render children()}
</main>

<style>
	main {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
	}
	.error-banner {
		background: #7f1d1d;
		color: #fecaca;
		padding: 12px 16px;
		font-size: 13px;
		text-align: center;
	}
	.error-banner code {
		background: rgba(0, 0, 0, 0.3);
		padding: 2px 6px;
		border-radius: 4px;
	}
</style>

<script lang="ts">
	import { appState } from '$lib/state.svelte';

	const isVisible = $derived(
		appState.webcamStream !== null &&
			(appState.recordingState === 'recording' || appState.recordingState === 'paused')
	);

	const position = $derived(appState.config.preferences.webcam_position ?? 'bottom-right');

	function togglePosition() {
		appState.config.preferences.webcam_position =
			position === 'bottom-left' ? 'bottom-right' : 'bottom-left';
	}

	let videoEl: HTMLVideoElement | undefined = $state();

	$effect(() => {
		if (videoEl && appState.webcamStream) {
			videoEl.srcObject = appState.webcamStream;
		} else if (videoEl) {
			videoEl.srcObject = null;
		}
	});
</script>

{#if isVisible}
	<div
		class="webcam-bubble"
		class:bottom-left={position === 'bottom-left'}
		class:bottom-right={position === 'bottom-right'}
	>
		<!-- svelte-ignore a11y_media_has_caption -->
		<video bind:this={videoEl} autoplay playsinline muted class="webcam-video"></video>
		<button class="position-toggle" onclick={togglePosition} aria-label="Move webcam bubble">
			{position === 'bottom-left' ? '\u2192' : '\u2190'}
		</button>
	</div>
{/if}

<style>
	.webcam-bubble {
		position: fixed;
		z-index: 1000;
		width: 120px;
		height: 120px;
		border-radius: 50%;
		overflow: hidden;
		border: 3px solid #334155;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
		transition: all 0.3s ease;
	}

	.webcam-bubble.bottom-left {
		bottom: 24px;
		left: 24px;
	}

	.webcam-bubble.bottom-right {
		bottom: 24px;
		right: 24px;
	}

	.webcam-video {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transform: scaleX(-1);
		display: block;
	}

	.position-toggle {
		position: absolute;
		top: 4px;
		right: 4px;
		width: 24px;
		height: 24px;
		background: rgba(15, 23, 42, 0.7);
		border: 1px solid #334155;
		border-radius: 50%;
		color: #f1f5f9;
		font-size: 12px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0;
		transition: opacity 0.2s;
	}

	.webcam-bubble:hover .position-toggle {
		opacity: 1;
	}

	.position-toggle:hover {
		background: rgba(15, 23, 42, 0.9);
		border-color: #475569;
	}
</style>

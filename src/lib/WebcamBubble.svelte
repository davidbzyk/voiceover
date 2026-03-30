<script lang="ts">
	import { appState } from '$lib/state.svelte';
	import { onDestroy } from 'svelte';

	// Live webcam preview bubble using a canvas that draws from the compositor's
	// shared webcamVideoEl (already decoding for the recorded output). This avoids
	// a second independent video decode pipeline that would waste ~2-5% CPU.

	const PREVIEW_SIZE = 120;
	const PREVIEW_FPS = 15;
	const FRAME_INTERVAL = 1000 / PREVIEW_FPS;

	const isVisible = $derived(
		appState.webcamStream !== null &&
			(appState.recordingState === 'recording' || appState.recordingState === 'paused')
	);

	const position = $derived(appState.config.preferences.webcam_position ?? 'bottom-right');

	function togglePosition() {
		appState.config.preferences.webcam_position =
			position === 'bottom-left' ? 'bottom-right' : 'bottom-left';
		appState.saveConfig();
	}

	let canvasEl: HTMLCanvasElement | undefined = $state();
	let animFrameId = 0;

	function startPreviewLoop() {
		let lastFrameTime = 0;

		function drawPreview(timestamp: number) {
			const videoEl = appState.webcamVideoEl;
			if (!canvasEl || !videoEl) {
				setTimeout(() => { animFrameId = requestAnimationFrame(drawPreview); }, 100);
				return;
			}

			if (timestamp - lastFrameTime < FRAME_INTERVAL) {
				animFrameId = requestAnimationFrame(drawPreview);
				return;
			}
			lastFrameTime = timestamp;

			const ctx = canvasEl.getContext('2d');
			if (!ctx) {
				animFrameId = requestAnimationFrame(drawPreview);
				return;
			}

			try {
				const vw = videoEl.videoWidth || 640;
				const vh = videoEl.videoHeight || 480;
				const srcSize = Math.min(vw, vh);
				const sx = (vw - srcSize) / 2;
				const sy = (vh - srcSize) / 2;

				ctx.save();
				// Mirror horizontally (selfie-cam effect)
				ctx.translate(PREVIEW_SIZE, 0);
				ctx.scale(-1, 1);
				ctx.drawImage(videoEl, sx, sy, srcSize, srcSize, 0, 0, PREVIEW_SIZE, PREVIEW_SIZE);
				ctx.restore();
			} catch {
				// Video element may not be ready yet — skip this frame
			}

			animFrameId = requestAnimationFrame(drawPreview);
		}

		animFrameId = requestAnimationFrame(drawPreview);
	}

	function stopPreviewLoop() {
		if (animFrameId) {
			cancelAnimationFrame(animFrameId);
			animFrameId = 0;
		}
	}

	$effect(() => {
		if (canvasEl && isVisible) {
			startPreviewLoop();
			return () => {
				stopPreviewLoop();
			};
		}
	});

	onDestroy(() => {
		stopPreviewLoop();
		if (appState.webcamStream) {
			appState.webcamStream.getTracks().forEach(t => t.stop());
			appState.webcamStream = null;
		}
	});
</script>

{#if isVisible}
	<div
		class="webcam-bubble"
		class:bottom-left={position === 'bottom-left'}
		class:bottom-right={position === 'bottom-right'}
	>
		<canvas
			bind:this={canvasEl}
			width={PREVIEW_SIZE}
			height={PREVIEW_SIZE}
			class="webcam-canvas"
		></canvas>
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

	.webcam-canvas {
		width: 100%;
		height: 100%;
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

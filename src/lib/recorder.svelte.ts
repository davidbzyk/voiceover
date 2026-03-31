// NOTE: The webcam overlay uses a single decoded video element shared between:
// 1. This compositor (canvas-based, burned into recorded output)
// 2. WebcamBubble.svelte (canvas preview, draws from appState.webcamVideoEl at 15fps)

import { logger } from './logger';
import { appState, isTauri } from './state.svelte';
import { blobStore } from './blobStore';

let mediaRecorder: MediaRecorder | null = null;
let audioRecorder: MediaRecorder | null = null;
let screenStream: MediaStream | null = null;
let audioStream: MediaStream | null = null;
let chunkIndex = 0;
let sessionId = '';

// Canvas compositor for webcam overlay in recorded output
let compositorCanvas: HTMLCanvasElement | null = null;
let compositorCtx: CanvasRenderingContext2D | null = null;
let screenVideoEl: HTMLVideoElement | null = null;
let webcamVideoEl: HTMLVideoElement | null = null;
let compositorFrameId = 0;

// Region capture state
let regionRect: RegionRect | null = null;
let regionResolve: ((rect: RegionRect | null) => void) | null = null;

// Browser mode: collect chunks in memory
let recordedChunks: Blob[] = [];
let audioChunks: Blob[] = [];

import { tauriInvoke } from './tauri';

export function generateSessionId(): string {
	return `rec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function selectVideoMimeType(): string {
	if (typeof MediaRecorder === 'undefined') return '';
	if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')) return 'video/webm;codecs=vp8,opus';
	if (MediaRecorder.isTypeSupported('video/webm')) return 'video/webm';
	return '';
}

export type CaptureMode = 'fullscreen' | 'window' | 'region';
export type RegionRect = { x: number; y: number; width: number; height: number };

/** Map app capture mode to a displaySurface hint for getDisplayMedia's picker UI */
export function captureModeToDisplaySurface(mode: CaptureMode): string {
	// 'region' captures a full monitor first, then crops via canvas
	return mode === 'window' ? 'window' : 'monitor';
}

/* v8 ignore start -- WebRTC recording requires browser runtime */
export async function startRecording(
	captureMode: CaptureMode,
	audioDeviceId?: string,
	webcamEnabled?: boolean
): Promise<void> {
	sessionId = generateSessionId();
	chunkIndex = 0;
	recordedChunks = [];
	audioChunks = [];

	try {
		if (!navigator.mediaDevices?.getDisplayMedia) {
			throw new Error(
				'Screen capture is not supported in this environment. ' +
					'Use browser mode (open in Chrome) or the Tauri desktop app.'
			);
		}

		// Request screen capture — displaySurface hints Chrome to pre-select the matching picker tab
		const displayMediaOptions: DisplayMediaStreamOptions = {
			video: {
				displaySurface: captureModeToDisplaySurface(captureMode),
				frameRate: { ideal: 30 }
			} as MediaTrackConstraints,
			audio: false
		};

		logger.recordingStart(captureMode);

		// Trigger getDisplayMedia first (needs user gesture), then minimize window
		const displayPromise = navigator.mediaDevices.getDisplayMedia(displayMediaOptions);

		// In Tauri fullscreen/region mode, minimize window to reveal macOS's
		// "Share This Screen" button (hidden behind app window on main monitor)
		let tauriWindow: Awaited<ReturnType<typeof import('@tauri-apps/api/window').getCurrentWindow>> | null = null;
		if (isTauri() && captureMode !== 'window') {
			try {
				const { getCurrentWindow } = await import('@tauri-apps/api/window');
				tauriWindow = getCurrentWindow();
				await tauriWindow.minimize();
			} catch (err) { logger.warn('record', 'Failed to minimize window for screen picker', err); }
		}

		screenStream = await displayPromise;

		if (tauriWindow) {
			try {
				await tauriWindow.unminimize();
				await tauriWindow.setFocus();
			} catch (err) { logger.warn('record', 'Failed to restore window after screen selection', err); }
		}

		logger.info('record', `Screen stream: ${screenStream.getVideoTracks()[0]?.label}`);

		// Stop recording if screen sharing ends externally (e.g. user clicks OS "Stop Sharing")
		screenStream.getVideoTracks()[0]?.addEventListener('ended', () => {
			logger.warn('record', 'Screen track ended externally');
			cancelRecording();
			appState.recordingState = 'ready';
			appState.errorMessage = 'Screen sharing was stopped';
		});

		// Region mode: grab a frame for the selection overlay, then wait for user to draw a rectangle
		if (captureMode === 'region') {
			const track = screenStream.getVideoTracks()[0];
			const settings = track.getSettings();
			const frameW = settings.width || 1920;
			const frameH = settings.height || 1080;

			// Grab one frame for the region selector background
			const tmpCanvas = document.createElement('canvas');
			tmpCanvas.width = frameW;
			tmpCanvas.height = frameH;
			const tmpVideo = document.createElement('video');
			tmpVideo.srcObject = screenStream;
			tmpVideo.muted = true;
			await tmpVideo.play();
			// Wait one frame for the video to render
			await new Promise((r) => requestAnimationFrame(r));
			const tmpCtx = tmpCanvas.getContext('2d');
			if (!tmpCtx) throw new Error('Failed to create canvas context for region screenshot');
			tmpCtx.drawImage(tmpVideo, 0, 0, frameW, frameH);
			tmpVideo.pause();
			tmpVideo.srcObject = null;

			appState.regionScreenshot = tmpCanvas.toDataURL('image/jpeg', 0.8);
			appState.recordingState = 'selecting-region';

			// Wait for user to draw a selection rectangle (resolved by confirmRegionSelection)
			const selectedRegion = await new Promise<RegionRect | null>((resolve) => {
				regionResolve = resolve;
			});
			regionResolve = null;
			appState.regionScreenshot = '';
			// Wait for the overlay to leave the screen before the compositor starts
			await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

			if (!selectedRegion) {
				// User cancelled region selection — not an error, just reset
				cleanup();
				appState.recordingState = 'ready';
				return;
			}
			regionRect = selectedRegion;
		}

		// Request microphone audio
		const audioConstraints: MediaStreamConstraints = {
			audio: audioDeviceId ? { deviceId: { exact: audioDeviceId } } : true,
			video: false
		};

		audioStream = await navigator.mediaDevices.getUserMedia(audioConstraints);
		logger.info('record', `Audio stream: ${audioStream.getAudioTracks()[0]?.label}`);

		// Get webcam stream if enabled
		if (webcamEnabled) {
			appState.webcamStream = await getWebcamStream();
		}

		// Determine video tracks: use canvas compositor if webcam overlay or region crop is active
		let videoTracks: MediaStreamTrack[];

		if ((appState.webcamStream || regionRect) && screenStream) {
			// Set up canvas compositor for region cropping and/or webcam overlay
			const screenTrack = screenStream.getVideoTracks()[0];
			const settings = screenTrack.getSettings();
			const canvasW = settings.width || 1920;
			const canvasH = settings.height || 1080;

			compositorCanvas = document.createElement('canvas');
			compositorCanvas.width = canvasW;
			compositorCanvas.height = canvasH;
			compositorCtx = compositorCanvas.getContext('2d', { alpha: false, desynchronized: true });
			if (!compositorCtx) {
				throw new Error('Failed to create 2D canvas context for webcam compositor');
			}

			// Hidden video elements to draw from
			screenVideoEl = document.createElement('video');
			screenVideoEl.srcObject = screenStream;
			screenVideoEl.muted = true;
			await screenVideoEl.play();
			// Wait for the first frame to decode — without this, the compositor
			// draws black frames until the video element produces decoded output
			await new Promise<void>((resolve) => {
				if (screenVideoEl!.videoWidth > 0) { resolve(); return; }
				screenVideoEl!.addEventListener('loadeddata', () => resolve(), { once: true });
			});
			if (regionRect) {
				// Region mode: canvas matches the cropped region size
				compositorCanvas.width = regionRect.width;
				compositorCanvas.height = regionRect.height;
				logger.info('record', `Region compositor: ${regionRect.width}x${regionRect.height}`);
			} else {
				compositorCanvas.width = screenVideoEl.videoWidth || canvasW;
				compositorCanvas.height = screenVideoEl.videoHeight || canvasH;

				// Cap compositor resolution — recording bitrate (2.5Mbps) is ~1080p quality,
				// so compositing at native 4K/Retina resolution wastes CPU
				const MAX_COMPOSITOR_WIDTH = 1920;
				const MAX_COMPOSITOR_HEIGHT = 1080;
				const scale = Math.min(MAX_COMPOSITOR_WIDTH / compositorCanvas.width, MAX_COMPOSITOR_HEIGHT / compositorCanvas.height, 1);
				if (scale < 1) {
					compositorCanvas.width = Math.round(compositorCanvas.width * scale);
					compositorCanvas.height = Math.round(compositorCanvas.height * scale);
					logger.info('record', `Compositor downscaled to ${compositorCanvas.width}x${compositorCanvas.height}`);
				}
			}

			if (appState.webcamStream) {
				webcamVideoEl = document.createElement('video');
				webcamVideoEl.srcObject = appState.webcamStream;
				webcamVideoEl.muted = true;
				await webcamVideoEl.play();
			}

			// Share the decoded video element with WebcamBubble to avoid dual decode
			if (webcamVideoEl) appState.webcamVideoEl = webcamVideoEl;

			// Draw the first frame synchronously so captureStream doesn't
			// start with a black canvas (rAF hasn't fired yet)
			const w = compositorCanvas.width;
			const h = compositorCanvas.height;
			if (regionRect) {
				compositorCtx.drawImage(screenVideoEl, regionRect.x, regionRect.y, regionRect.width, regionRect.height, 0, 0, w, h);
			} else {
				compositorCtx.drawImage(screenVideoEl, 0, 0, w, h);
			}

			startCompositorLoop();

			if (!('captureStream' in compositorCanvas)) {
				logger.warn('record', 'captureStream not available — recording without webcam overlay');
				videoTracks = screenStream.getVideoTracks();
			} else {
				const canvasStream = compositorCanvas.captureStream(30);
				videoTracks = canvasStream.getVideoTracks();
				logger.info('record', `Compositor: ${compositorCanvas.width}x${compositorCanvas.height}${webcamVideoEl ? ' with webcam overlay' : ''}`);
			}
		} else {
			if (!screenStream) throw new Error('Screen capture was lost');
			videoTracks = screenStream.getVideoTracks();
		}

		if (!screenStream || !audioStream) throw new Error('Media streams were lost');

		// Combine video + mic audio into one stream
		const combinedStream = new MediaStream([
			...videoTracks,
			...audioStream.getAudioTracks()
		]);

		// Determine supported MIME type
		const mimeType = selectVideoMimeType();

		mediaRecorder = new MediaRecorder(combinedStream, {
			...(mimeType ? { mimeType } : {}),
			videoBitsPerSecond: 2_500_000
		});

		mediaRecorder.ondataavailable = async (event) => {
			if (event.data.size > 0) {
				logger.recordingChunk(chunkIndex, event.data.size);
				if (isTauri()) {
					const buffer = await event.data.arrayBuffer();
					const bytes = new Uint8Array(buffer);
					await tauriInvoke('save_recording_chunk', {
						sessionId,
						chunk: bytes,
						chunkIndex: chunkIndex++
					});
				} else {
					recordedChunks.push(event.data);
					chunkIndex++;
				}
			}
		};

		// Capture in 5-second chunks for progressive saving (reduces IPC overhead vs 1s)
		mediaRecorder.start(5000);

		// Record audio separately (clean audio-only track for ElevenLabs S2S)
		if (!isTauri()) {
			const audioOnlyStream = new MediaStream([...audioStream!.getAudioTracks()]);
			const audioMime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
				? 'audio/webm;codecs=opus'
				: '';
			audioRecorder = new MediaRecorder(audioOnlyStream, {
				...(audioMime ? { mimeType: audioMime } : {})
			});
			audioRecorder.ondataavailable = (event) => {
				if (event.data.size > 0) audioChunks.push(event.data);
			};
			audioRecorder.start(5000);
			logger.info('record', 'Audio-only recorder started for S2S');
		}

	} catch (err) {
		cleanup();
		throw err;
	}
}

/* v8 ignore stop */

/** Webcam bubble dimensions — 12% of canvas width, clamped to 100-240px for visibility at all resolutions */
export function computeWebcamBubbleRect(
	canvasW: number,
	canvasH: number,
	position: 'bottom-left' | 'bottom-right'
): { x: number; y: number; diameter: number; centerX: number; centerY: number; radius: number } {
	const diameter = Math.max(100, Math.min(240, canvasW * 0.12));
	const margin = Math.max(16, canvasW * 0.02);
	const x = position === 'bottom-right' ? canvasW - diameter - margin : margin;
	const y = canvasH - diameter - margin;
	return { x, y, diameter, centerX: x + diameter / 2, centerY: y + diameter / 2, radius: diameter / 2 };
}

function startCompositorLoop() {
	let lastFrameTime = 0;
	const FRAME_INTERVAL = 1000 / 30;

	function drawFrame(timestamp: number) {
		if (!compositorCtx || !compositorCanvas || !screenVideoEl) return;

		if (timestamp - lastFrameTime < FRAME_INTERVAL) {
			compositorFrameId = requestAnimationFrame(drawFrame);
			return;
		}
		lastFrameTime = timestamp;

		try {
			const w = compositorCanvas.width;
			const h = compositorCanvas.height;

			// Draw screen capture (cropped to region if active)
			if (regionRect) {
				compositorCtx.drawImage(screenVideoEl, regionRect.x, regionRect.y, regionRect.width, regionRect.height, 0, 0, w, h);
			} else {
				compositorCtx.drawImage(screenVideoEl, 0, 0, w, h);
			}

			// Draw circular webcam overlay
			if (webcamVideoEl && appState.webcamStream) {
				const position = appState.config.preferences.webcam_position ?? 'bottom-right';
				const { x, y, diameter, centerX, centerY, radius } = computeWebcamBubbleRect(w, h, position);

				// Crop webcam to center square for cover-fit
				const vw = webcamVideoEl.videoWidth || 640;
				const vh = webcamVideoEl.videoHeight || 480;
				const srcSize = Math.min(vw, vh);
				const sx = (vw - srcSize) / 2;
				const sy = (vh - srcSize) / 2;

				// Mirror webcam horizontally (selfie-cam effect) so user movements appear natural
				compositorCtx.save();
				compositorCtx.beginPath();
				compositorCtx.arc(centerX, centerY, radius, 0, Math.PI * 2);
				compositorCtx.clip();
				compositorCtx.translate(centerX, 0);
				compositorCtx.scale(-1, 1);
				compositorCtx.translate(-centerX, 0);
				compositorCtx.drawImage(webcamVideoEl, sx, sy, srcSize, srcSize, x, y, diameter, diameter);
				compositorCtx.restore();

				// Border ring
				compositorCtx.beginPath();
				compositorCtx.arc(centerX, centerY, radius, 0, Math.PI * 2);
				compositorCtx.strokeStyle = 'rgba(51, 65, 85, 0.8)';
				compositorCtx.lineWidth = 3;
				compositorCtx.stroke();
			}
		} catch (err) {
			logger.warn('record', 'Compositor frame draw failed', err);
		}

		compositorFrameId = requestAnimationFrame(drawFrame);
	}

	compositorFrameId = requestAnimationFrame(drawFrame);
}

/* v8 ignore start -- WebRTC webcam requires browser runtime */
async function getWebcamStream(): Promise<MediaStream | null> {
	try {
		return await navigator.mediaDevices.getUserMedia({
			video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 24 } },
			audio: false
		});
	} catch (err) {
		const msg = err instanceof DOMException
			? `Webcam unavailable: ${err.message}`
			: 'Webcam unavailable';
		logger.warn('webcam', msg);
		appState.errorMessage = msg + '. Recording without webcam.';
		return null;
	}
}

/* v8 ignore stop */

export function pauseRecording() {
	if (mediaRecorder?.state === 'recording') {
		mediaRecorder.pause();
		audioRecorder?.pause();
		if (compositorFrameId) {
			cancelAnimationFrame(compositorFrameId);
			compositorFrameId = 0;
		}
	}
}

export function resumeRecording() {
	if (mediaRecorder?.state === 'paused') {
		mediaRecorder.resume();
		audioRecorder?.resume();
		if (compositorCanvas && !compositorFrameId) {
			startCompositorLoop();
		}
	}
}

/* v8 ignore start -- WebRTC stop/cleanup requires browser runtime */
export async function stopRecording(): Promise<string> {
	return new Promise((resolve, reject) => {
		if (!mediaRecorder) {
			reject(new Error('No active recording'));
			return;
		}

		// Stop audio recorder first
		if (audioRecorder?.state !== 'inactive') {
			audioRecorder?.stop();
		}

		mediaRecorder.onstop = async () => {
			try {
				if (isTauri()) {
					const path = await tauriInvoke<string>('finalize_recording', { sessionId });
					logger.recordingStop(chunkIndex);
					logger.info('record', `Finalized: ${path}`);
					cleanup();
					resolve(path);
				} else {
					const videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
					const audioBlobOnly = new Blob(audioChunks, { type: 'audio/webm' });
					const url = URL.createObjectURL(videoBlob);
					logger.recordingStop(chunkIndex);
					logger.info('record', `Video: ${(videoBlob.size / 1024 / 1024).toFixed(1)}MB`);
					logger.info('record', `Audio: ${(audioBlobOnly.size / 1024).toFixed(0)}KB`);
					blobStore.setVideo(videoBlob);
					blobStore.setAudio(audioBlobOnly);
					recordedChunks = [];
					audioChunks = [];
					cleanup();
					resolve(url);
				}
			} catch (e) {
				cleanup();
				reject(e);
			}
		};

		mediaRecorder.stop();
	});
}

export function cancelRecording() {
	recordedChunks = [];
	audioChunks = [];
	if (audioRecorder?.state !== 'inactive') audioRecorder?.stop();
	cleanup();
}

function cleanup() {
	if (compositorFrameId) {
		cancelAnimationFrame(compositorFrameId);
		compositorFrameId = 0;
	}
	if (screenVideoEl) {
		screenVideoEl.pause();
		screenVideoEl.srcObject = null;
	}
	if (webcamVideoEl) {
		webcamVideoEl.pause();
		webcamVideoEl.srcObject = null;
	}
	screenVideoEl = null;
	webcamVideoEl = null;
	appState.webcamVideoEl = null;
	compositorCanvas = null;
	compositorCtx = null;
	// Stop all media tracks individually — screen, audio, and webcam are separate streams with independent lifecycles
	screenStream?.getTracks().forEach((t) => t.stop());
	audioStream?.getTracks().forEach((t) => t.stop());
	appState.webcamStream?.getTracks().forEach((t) => t.stop());
	screenStream = null;
	audioStream = null;
	appState.webcamStream = null;
	mediaRecorder = null;
	audioRecorder = null;
	// Resolve any pending region selection before nullifying to prevent dangling promises
	if (regionResolve) regionResolve(null);
	regionRect = null;
	regionResolve = null;
	appState.regionScreenshot = '';
}

/* v8 ignore stop */

export async function getAudioDevices(): Promise<MediaDeviceInfo[]> {
	const devices = await navigator.mediaDevices.enumerateDevices();
	return devices.filter((d) => d.kind === 'audioinput');
}

/** Map a CSS-space selection rectangle to source video pixel coordinates */
export function mapSelectionToSource(
	sel: RegionRect,
	displayW: number,
	displayH: number,
	sourceW: number,
	sourceH: number
): RegionRect {
	if (displayW === 0 || displayH === 0) {
		return { x: 0, y: 0, width: 0, height: 0 };
	}
	const scaleX = sourceW / displayW;
	const scaleY = sourceH / displayH;
	return {
		x: Math.round(sel.x * scaleX),
		y: Math.round(sel.y * scaleY),
		width: Math.round(sel.width * scaleX),
		height: Math.round(sel.height * scaleY)
	};
}

/** Called by RegionSelector when user finishes drawing a selection rectangle */
export function confirmRegionSelection(rect: RegionRect): void {
	if (regionResolve) {
		regionResolve(rect);
	}
}

/** Called by RegionSelector when user cancels (Escape key) — resolves with null to exit cleanly */
export function cancelRegionSelection(): void {
	if (regionResolve) {
		regionResolve(null);
	}
}

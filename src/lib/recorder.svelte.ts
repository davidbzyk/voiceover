import { logger } from './logger';
import { appState, isTauri } from './state.svelte';

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

// Browser mode: collect chunks in memory
let recordedChunks: Blob[] = [];
let audioChunks: Blob[] = [];

async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
	const { invoke } = await import('@tauri-apps/api/core');
	return invoke<T>(cmd, args);
}

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

/* v8 ignore start -- WebRTC recording requires browser runtime */
export async function startRecording(
	captureMode: CaptureMode,
	audioDeviceId?: string,
	webcamEnabled?: boolean
): Promise<MediaStream | null> {
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

		// Request screen capture — OS provides the picker dialog
		const displayMediaOptions: DisplayMediaStreamOptions = {
			video: {
				frameRate: { ideal: 30 }
			},
			audio: false
		};

		logger.recordingStart(captureMode);
		screenStream = await navigator.mediaDevices.getDisplayMedia(displayMediaOptions);
		logger.info('record', `Screen stream: ${screenStream.getVideoTracks()[0]?.label}`);

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

		// Determine video tracks: use canvas compositor if webcam is active
		let videoTracks: MediaStreamTrack[];

		if (appState.webcamStream) {
			// Set up canvas compositor to overlay webcam onto screen capture
			const screenTrack = screenStream.getVideoTracks()[0];
			const settings = screenTrack.getSettings();
			const canvasW = settings.width || 1920;
			const canvasH = settings.height || 1080;

			compositorCanvas = document.createElement('canvas');
			compositorCanvas.width = canvasW;
			compositorCanvas.height = canvasH;
			compositorCtx = compositorCanvas.getContext('2d');

			if (!compositorCtx) {
				logger.error('record', 'Failed to get 2D canvas context — falling back to screen-only');
				compositorCanvas = null;
				videoTracks = screenStream.getVideoTracks();
			} else {
				// Hidden video elements to draw from
				screenVideoEl = document.createElement('video');
				screenVideoEl.srcObject = screenStream;
				screenVideoEl.muted = true;
				await screenVideoEl.play();

				webcamVideoEl = document.createElement('video');
				webcamVideoEl.srcObject = appState.webcamStream;
				webcamVideoEl.muted = true;
				await webcamVideoEl.play();

				startCompositorLoop();

				const canvasStream = compositorCanvas.captureStream(30);
				videoTracks = canvasStream.getVideoTracks();
				logger.info('record', `Compositor: ${canvasW}x${canvasH} with webcam overlay`);
			}
		} else {
			videoTracks = screenStream.getVideoTracks();
		}

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

		// Capture in 1-second chunks for progressive saving
		mediaRecorder.start(1000);

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
			audioRecorder.start(1000);
			logger.info('record', 'Audio-only recorder started for S2S');
		}

		return appState.webcamStream;
	} catch (err) {
		cleanup();
		throw err;
	}
}

/* v8 ignore stop */

function startCompositorLoop() {
	function drawFrame() {
		if (!compositorCtx || !compositorCanvas || !screenVideoEl) return;

		try {
			const w = compositorCanvas.width;
			const h = compositorCanvas.height;

			// Draw screen capture
			compositorCtx.drawImage(screenVideoEl, 0, 0, w, h);

			// Draw circular webcam overlay
			if (webcamVideoEl && appState.webcamStream) {
				const diameter = Math.max(100, Math.min(240, w * 0.12));
				const margin = Math.max(16, w * 0.02);
				const position = appState.config.preferences.webcam_position ?? 'bottom-right';

				const x = position === 'bottom-right' ? w - diameter - margin : margin;
				const y = h - diameter - margin;
				const centerX = x + diameter / 2;
				const centerY = y + diameter / 2;
				const radius = diameter / 2;

				// Crop webcam to center square for cover-fit
				const vw = webcamVideoEl.videoWidth || 640;
				const vh = webcamVideoEl.videoHeight || 480;
				const srcSize = Math.min(vw, vh);
				const sx = (vw - srcSize) / 2;
				const sy = (vh - srcSize) / 2;

				// Circular clip + mirror
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

	drawFrame();
}

/* v8 ignore start -- WebRTC webcam requires browser runtime */
async function getWebcamStream(): Promise<MediaStream | null> {
	try {
		return await navigator.mediaDevices.getUserMedia({
			video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 24 } },
			audio: false
		});
	} catch {
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
			reject('No active recording');
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
					(window as any).__voiceover_blob = videoBlob;
					(window as any).__voiceover_audio_blob = audioBlobOnly;
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
	compositorCanvas = null;
	compositorCtx = null;
	screenStream?.getTracks().forEach((t) => t.stop());
	audioStream?.getTracks().forEach((t) => t.stop());
	appState.webcamStream?.getTracks().forEach((t) => t.stop());
	screenStream = null;
	audioStream = null;
	appState.webcamStream = null;
	mediaRecorder = null;
	audioRecorder = null;
}

/* v8 ignore stop */

export async function getAudioDevices(): Promise<MediaDeviceInfo[]> {
	const devices = await navigator.mediaDevices.enumerateDevices();
	return devices.filter((d) => d.kind === 'audioinput');
}

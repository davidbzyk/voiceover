import { logger } from './logger';
import { isTauri } from './state.svelte';

let mediaRecorder: MediaRecorder | null = null;
let audioRecorder: MediaRecorder | null = null;
let screenStream: MediaStream | null = null;
let audioStream: MediaStream | null = null;
let chunkIndex = 0;
let sessionId = '';

// Browser mode: collect chunks in memory
let recordedChunks: Blob[] = [];
let audioChunks: Blob[] = [];

async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
	const { invoke } = await import('@tauri-apps/api/core');
	return invoke<T>(cmd, args);
}

function generateSessionId(): string {
	return `rec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export type CaptureMode = 'fullscreen' | 'window' | 'region';

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

		// Combine screen video + mic audio into one stream
		const combinedStream = new MediaStream([
			...screenStream.getVideoTracks(),
			...audioStream.getAudioTracks()
		]);

		// Determine supported MIME type
		const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
			? 'video/webm;codecs=vp8,opus'
			: MediaRecorder.isTypeSupported('video/webm')
				? 'video/webm'
				: '';

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

		return webcamEnabled ? await getWebcamStream() : null;
	} catch (err) {
		cleanup();
		throw err;
	}
}

async function getWebcamStream(): Promise<MediaStream | null> {
	try {
		return await navigator.mediaDevices.getUserMedia({
			video: { width: 160, height: 120, frameRate: 24 },
			audio: false
		});
	} catch {
		return null;
	}
}

export function pauseRecording() {
	if (mediaRecorder?.state === 'recording') {
		mediaRecorder.pause();
		audioRecorder?.pause();
	}
}

export function resumeRecording() {
	if (mediaRecorder?.state === 'paused') {
		mediaRecorder.resume();
		audioRecorder?.resume();
	}
}

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
	screenStream?.getTracks().forEach((t) => t.stop());
	audioStream?.getTracks().forEach((t) => t.stop());
	screenStream = null;
	audioStream = null;
	mediaRecorder = null;
	audioRecorder = null;
}

export async function getAudioDevices(): Promise<MediaDeviceInfo[]> {
	const devices = await navigator.mediaDevices.enumerateDevices();
	return devices.filter((d) => d.kind === 'audioinput');
}

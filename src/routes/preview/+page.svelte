<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState, isTauri } from '$lib/state.svelte';
	import { logger } from '$lib/logger';

	import { onMount } from 'svelte';

	let isProcessing = $state(false);
	let processingError = $state('');
	let transformedAudioUrl = $state('');
	let videoSrc = $state('');

	onMount(async () => {
		if (!appState.recordingPath) return;
		if (appState.recordingPath.startsWith('blob:')) {
			videoSrc = appState.recordingPath;
		} else if (isTauri()) {
			// Read the file as bytes and create a blob URL
			// (asset protocol is unreliable in WKWebView)
			try {
				const { invoke } = await import('@tauri-apps/api/core');
				const bytes = await invoke<number[]>('read_file_bytes', {
					path: appState.recordingPath
				});
				const blob = new Blob([new Uint8Array(bytes)], { type: 'video/webm' });
				videoSrc = URL.createObjectURL(blob);
			} catch (e) {
				logger.error('preview', 'Failed to load video preview', e);
			}
		}
	});

	async function processAndSave() {
		isProcessing = true;
		processingError = '';
		appState.processingProgress = 0;
		appState.processingStage = 'Starting...';
		logger.pipelineStart(appState.config.preferences.voice_replacement_enabled);

		try {
			if (isTauri()) {
				await processViaTauri();
			} else {
				await processViaBrowser();
			}
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			processingError = msg;
			logger.pipelineError(msg);
		}
		isProcessing = false;
	}

	async function processViaTauri() {
		const { invoke, Channel } = await import('@tauri-apps/api/core');

		type PipelineEvent =
			| { event: 'progress'; data: { stage: string; percent: number } }
			| { event: 'complete'; data: { outputPath: string } }
			| { event: 'error'; data: { message: string } };

		const onEvent = new Channel<PipelineEvent>();
		onEvent.onmessage = (msg) => {
			if (msg.event === 'progress') {
				appState.processingProgress = msg.data.percent;
				appState.processingStage = msg.data.stage;
				logger.pipelineStage(msg.data.stage, msg.data.percent);
			} else if (msg.event === 'complete') {
				appState.outputPath = msg.data.outputPath;
				appState.recordingState = 'saved';
				logger.pipelineComplete(msg.data.outputPath);
				isProcessing = false;
			} else if (msg.event === 'error') {
				processingError = msg.data.message;
				logger.pipelineError(msg.data.message);
				isProcessing = false;
			}
		};

		const result = await invoke<string>('process_recording', {
			recordingPath: appState.recordingPath,
			voiceReplacement: appState.config.preferences.voice_replacement_enabled,
			voiceId: appState.selectedVoice?.id ?? null,
			onEvent
		});
		appState.outputPath = result;
		appState.recordingState = 'saved';
	}

	async function processViaBrowser() {
		const blob = (window as any).__voiceover_blob as Blob | undefined;
		if (!blob) {
			throw new Error('No recording data found');
		}

		if (!appState.config.preferences.voice_replacement_enabled) {
			// No voice replacement — just download the raw recording
			appState.processingStage = 'Preparing download...';
			appState.processingProgress = 100;
			downloadBlob(blob, `voiceover-${Date.now()}.webm`);
			appState.outputPath = 'Downloaded';
			appState.recordingState = 'saved';
			logger.pipelineComplete('browser download (raw)');
			return;
		}

		// Voice replacement in browser mode
		const apiKey = appState.config.elevenlabs_api_key.trim();
		const voice = appState.selectedVoice;
		if (!apiKey) throw new Error('ElevenLabs API key not set — go to Settings');
		if (!voice) throw new Error('No voice selected — go to Settings');

		// Step 1: Get the separate audio-only recording
		appState.processingStage = 'Preparing audio...';
		appState.processingProgress = 10;
		logger.pipelineStage('Preparing audio', 10);

		// Use the audio-only blob recorded separately (clean, no video data)
		let audioBlob = (window as any).__voiceover_audio_blob as Blob | undefined;
		if (!audioBlob || audioBlob.size === 0) {
			logger.warn('pipeline', 'No separate audio blob, extracting from video');
			audioBlob = await extractAudioFromBlob(blob);
		}
		logger.info('pipeline', `Audio for S2S: ${(audioBlob.size / 1024).toFixed(0)}KB, type=${audioBlob.type}`);

		// Step 2: Send to ElevenLabs S2S
		appState.processingStage = 'Transforming voice...';
		appState.processingProgress = 20;
		logger.elevenLabsS2S(voice.id);

		const s2sStart = performance.now();
		const formData = new FormData();
		formData.append('audio', audioBlob, 'input.webm');
		formData.append('model_id', 'eleven_multilingual_sts_v2');
		formData.append('remove_background_noise', 'true');

		const s2sResp = await fetch(
			`https://api.elevenlabs.io/v1/speech-to-speech/${voice.id}?output_format=mp3_44100_128`,
			{
				method: 'POST',
				headers: { 'xi-api-key': apiKey },
				body: formData
			}
		);

		if (!s2sResp.ok) {
			const body = await s2sResp.text();
			throw new Error(`ElevenLabs S2S error ${s2sResp.status}: ${body}`);
		}

		const transformedBlob = await s2sResp.blob();
		logger.elevenLabsS2SDone(performance.now() - s2sStart);
		logger.info('pipeline', `Transformed audio: ${(transformedBlob.size / 1024).toFixed(0)}KB`);

		// Step 3: Splice video + new audio using ffmpeg.wasm
		appState.processingStage = 'Loading ffmpeg...';
		appState.processingProgress = 70;
		logger.pipelineStage('Loading ffmpeg.wasm', 70);

		const { FFmpeg } = await import('@ffmpeg/ffmpeg');
		const { fetchFile, toBlobURL } = await import('@ffmpeg/util');

		const ffmpegInstance = new FFmpeg();
		ffmpegInstance.on('log', ({ message }) => {
			logger.debug('ffmpeg', message);
		});
		ffmpegInstance.on('progress', ({ progress }) => {
			const pct = 75 + progress * 20;
			appState.processingProgress = pct;
		});

		// Load single-threaded ESM core
		// Use direct URL — Vite serves static/ at root, same origin = importable
		logger.info('ffmpeg', 'Loading core from /ffmpeg/...');
		try {
			await ffmpegInstance.load({
				coreURL: new URL('/ffmpeg/ffmpeg-core.js', window.location.origin).href,
				wasmURL: new URL('/ffmpeg/ffmpeg-core.wasm', window.location.origin).href
			});
		} catch (loadErr) {
			logger.warn('ffmpeg', `Direct load failed: ${loadErr}, trying toBlobURL fallback...`);
			const coreURL = await toBlobURL('/ffmpeg/ffmpeg-core.js', 'text/javascript');
			const wasmURL = await toBlobURL('/ffmpeg/ffmpeg-core.wasm', 'application/wasm');
			await ffmpegInstance.load({ coreURL, wasmURL });
		}

		logger.pipelineStage('Splicing video + audio', 75);
		appState.processingStage = 'Splicing video + audio...';

		await ffmpegInstance.writeFile('video.webm', await fetchFile(blob));
		await ffmpegInstance.writeFile('voice.mp3', await fetchFile(transformedBlob));

		// Mute first 0.5s of transformed audio (removes S2S startup squelch)
		// volume=0 for 0-0.5s, then fade in over 0.1s — keeps perfect sync
		await ffmpegInstance.exec([
			'-i', 'video.webm',
			'-i', 'voice.mp3',
			'-map', '0:v:0',
			'-map', '1:a:0',
			'-c:v', 'copy',
			'-af', 'volume=enable=\'between(t,0,0.5)\':volume=0,afade=t=in:st=0.5:d=0.1',
			'-c:a', 'libopus',
			'-b:a', '128k',
			'-shortest',
			'output.webm'
		]);

		const outputData = await ffmpegInstance.readFile('output.webm');
		const outputBlob = new Blob([outputData], { type: 'video/webm' });
		ffmpegInstance.terminate();

		appState.processingStage = 'Complete!';
		appState.processingProgress = 100;

		const filename = `voiceover-${Date.now()}.webm`;
		downloadBlob(outputBlob, filename);

		(window as any).__voiceover_blob = outputBlob;
		appState.outputPath = `Downloaded: ${filename}`;
		appState.recordingState = 'saved';
		logger.pipelineComplete(`browser: ${filename} (${(outputBlob.size / 1024 / 1024).toFixed(1)}MB)`);
	}

	async function extractAudioFromBlob(videoBlob: Blob): Promise<Blob> {
		const arrayBuffer = await videoBlob.arrayBuffer();
		const audioCtx = new AudioContext();

		try {
			const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
			await audioCtx.close();

			logger.info('pipeline', `Decoded audio: ${audioBuffer.duration.toFixed(1)}s, ${audioBuffer.sampleRate}Hz, ${audioBuffer.numberOfChannels}ch`);

			if (audioBuffer.duration > 300) {
				throw new Error(`Recording is ${Math.floor(audioBuffer.duration / 60)}m ${Math.floor(audioBuffer.duration % 60)}s — ElevenLabs S2S limit is 5 minutes. Record a shorter clip.`);
			}

			// Resample to 16kHz mono using OfflineAudioContext
			const targetRate = 16000;
			const targetLength = Math.ceil(audioBuffer.duration * targetRate);
			const offlineCtx = new OfflineAudioContext(1, targetLength, targetRate);
			const source = offlineCtx.createBufferSource();
			source.buffer = audioBuffer;
			source.connect(offlineCtx.destination);
			source.start();
			const rendered = await offlineCtx.startRendering();

			// Encode as proper WAV
			const wavBlob = encodeWav(rendered.getChannelData(0), targetRate);
			logger.info('pipeline', `WAV encoded: ${(wavBlob.size / 1024).toFixed(0)}KB, ${targetRate}Hz mono`);
			return wavBlob;
		} catch (err) {
			await audioCtx.close().catch(() => {});
			// Re-throw if it's our duration error
			if (err instanceof Error && err.message.includes('limit is 5 minutes')) throw err;
			// Fallback: send WebM directly (ElevenLabs can decode it)
			logger.warn('pipeline', `AudioContext decode failed: ${err}, sending WebM directly`);
			return new Blob([arrayBuffer], { type: 'audio/webm' });
		}
	}

	function encodeWav(samples: Float32Array, sampleRate: number): Blob {
		const buffer = new ArrayBuffer(44 + samples.length * 2);
		const view = new DataView(buffer);

		// WAV header
		const writeStr = (offset: number, str: string) => {
			for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
		};
		writeStr(0, 'RIFF');
		view.setUint32(4, 36 + samples.length * 2, true);
		writeStr(8, 'WAVE');
		writeStr(12, 'fmt ');
		view.setUint32(16, 16, true); // chunk size
		view.setUint16(20, 1, true); // PCM
		view.setUint16(22, 1, true); // mono
		view.setUint32(24, sampleRate, true);
		view.setUint32(28, sampleRate * 2, true); // byte rate
		view.setUint16(32, 2, true); // block align
		view.setUint16(34, 16, true); // bits per sample
		writeStr(36, 'data');
		view.setUint32(40, samples.length * 2, true);

		// Convert float32 to int16
		let offset = 44;
		for (let i = 0; i < samples.length; i++) {
			const s = Math.max(-1, Math.min(1, samples[i]));
			view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
			offset += 2;
		}

		return new Blob([buffer], { type: 'audio/wav' });
	}

	function downloadBlob(blob: Blob, filename: string) {
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		a.click();
		setTimeout(() => URL.revokeObjectURL(url), 5000);
	}

	let isUploading = $state(false);
	let driveLink = $state('');

	async function refreshDriveToken(): Promise<string> {
		const { client_id, client_secret, refresh_token } = appState.config.google_drive;
		if (!refresh_token) throw new Error('No refresh token — reconnect Google Drive in Settings');

		logger.info('drive', 'Refreshing access token...');
		const resp = await fetch('https://oauth2.googleapis.com/token', {
			method: 'POST',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body: new URLSearchParams({
				client_id,
				client_secret,
				refresh_token,
				grant_type: 'refresh_token'
			})
		});

		if (!resp.ok) {
			const body = await resp.text();
			throw new Error(`Token refresh failed: ${body}`);
		}

		const data = await resp.json();
		const newToken = data.access_token;
		const expiresIn = data.expires_in || 3600;
		appState.config.google_drive.access_token = newToken;
		appState.config.google_drive.expires_at = Math.floor(Date.now() / 1000) + expiresIn - 60;
		await appState.saveConfig();
		logger.info('drive', 'Access token refreshed');
		return newToken;
	}

	async function driveUploadWithToken(blob: Blob, accessToken: string): Promise<string> {
		const metadata = JSON.stringify({
			name: `voiceover-${Date.now()}.webm`,
			mimeType: 'video/webm'
		});

		const form = new FormData();
		form.append('metadata', new Blob([metadata], { type: 'application/json' }));
		form.append('file', blob);

		const resp = await fetch(
			'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink',
			{
				method: 'POST',
				headers: { Authorization: `Bearer ${accessToken}` },
				body: form
			}
		);

		if (!resp.ok) {
			const status = resp.status;
			const body = await resp.text();
			throw { status, body };
		}

		const data = await resp.json();

		// Make shareable
		await fetch(`https://www.googleapis.com/drive/v3/files/${data.id}/permissions`, {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${accessToken}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ type: 'anyone', role: 'reader' })
		});

		return data.webViewLink || '';
	}

	async function uploadToDrive() {
		if (!appState.config.google_drive.connected) return;
		isUploading = true;
		logger.driveUploadStart(appState.outputPath || 'blob');

		try {
			// Refresh token if expired (applies to both Tauri and browser mode)
			let token = appState.config.google_drive.access_token;
			const now = Math.floor(Date.now() / 1000);
			if (!appState.config.google_drive.expires_at || now >= appState.config.google_drive.expires_at) {
				logger.info('drive', 'Token expired, refreshing...');
				token = await refreshDriveToken();
			}

			if (isTauri()) {
				const { invoke, Channel } = await import('@tauri-apps/api/core');
				type DriveEvent =
					| { event: 'progress'; data: { percent: number } }
					| { event: 'complete'; data: { url: string } }
					| { event: 'error'; data: { message: string } };

				const onEvent = new Channel<DriveEvent>();
				onEvent.onmessage = (msg) => {
					if (msg.event === 'complete') driveLink = msg.data.url;
				};

				driveLink = await invoke<string>('upload_to_drive', {
					accessToken: token,
					filePath: appState.outputPath,
					onEvent
				});
			} else {
				const blob = (window as any).__voiceover_blob as Blob | undefined;
				if (!blob) throw new Error('No recording blob for upload');

				try {
					driveLink = await driveUploadWithToken(blob, token);
				} catch (err: any) {
					if (err?.status === 401) {
						// Token expired — refresh and retry
						token = await refreshDriveToken();
						driveLink = await driveUploadWithToken(blob, token);
					} else {
						throw new Error(`Drive upload failed: ${err?.status || ''} ${err?.body || err}`);
					}
				}
			}
			if (driveLink) logger.driveUploadDone(driveLink);
		} catch (err) {
			const msg = String(err);
			processingError = msg;
			logger.driveError(msg);
		}
		isUploading = false;
	}

	function discard() {
		appState.reset();
		goto('/');
	}

	function newRecording() {
		appState.reset();
		goto('/');
	}
</script>

<div class="preview">
	<div class="header">
		<h2>
			{#if appState.recordingState === 'saved'}
				✅ Saved
			{:else}
				Preview
			{/if}
		</h2>
	</div>

	<!-- Video preview -->
	{#if videoSrc}
		<div class="video-container">
			<video controls src={videoSrc} class="video-player">
				<track kind="captions" />
			</video>
		</div>
	{/if}

	<!-- Voice replacement toggle -->
	{#if appState.recordingState !== 'saved'}
		<div class="toggle-row">
			<div>
				<div class="toggle-label">🎙️ Replace Voice</div>
				<div class="toggle-hint">
					{appState.config.preferences.voice_replacement_enabled
						? `Using: ${appState.selectedVoice?.name ?? 'None'}`
						: 'Save raw recording'}
				</div>
			</div>
			<button
				class="toggle"
				class:active={appState.config.preferences.voice_replacement_enabled}
				onclick={() =>
					(appState.config.preferences.voice_replacement_enabled =
						!appState.config.preferences.voice_replacement_enabled)}
				disabled={isProcessing}
			>
				<div class="toggle-knob"></div>
			</button>
		</div>
	{/if}

	<!-- Processing progress -->
	{#if isProcessing}
		<div class="progress-section">
			<div class="progress-header">
				<span>{appState.processingStage}</span>
				<span>{Math.round(appState.processingProgress)}%</span>
			</div>
			<div class="progress-bar">
				<div class="progress-fill" style="width: {appState.processingProgress}%"></div>
			</div>
		</div>
	{/if}

	<!-- Error -->
	{#if processingError}
		<div class="error-box">
			<div>{processingError}</div>
			<button class="link-btn" onclick={() => (processingError = '')}>Dismiss</button>
		</div>
	{/if}

	<!-- Saved state -->
	{#if appState.recordingState === 'saved'}
		<div class="saved-info">
			<div class="saved-label">Saved to:</div>
			<div class="saved-path">{appState.outputPath}</div>
		</div>

		{#if driveLink}
			<div class="drive-link">
				<div class="saved-label">Drive link:</div>
				<a href={driveLink} class="link">{driveLink}</a>
			</div>
		{:else if appState.config.google_drive.connected}
			<button class="btn secondary" onclick={uploadToDrive} disabled={isUploading}>
				{isUploading ? 'Uploading...' : '☁️ Upload to Google Drive'}
			</button>
		{/if}

		<button class="btn primary" onclick={newRecording}>🎬 New Recording</button>
	{:else}
		<!-- Action buttons -->
		<div class="actions">
			<button class="btn primary" onclick={processAndSave} disabled={isProcessing}>
				{isProcessing ? 'Processing...' : '💾 Save MP4'}
			</button>
			<button class="btn secondary" onclick={discard} disabled={isProcessing}>🗑️ Discard</button>
		</div>
	{/if}
</div>

<style>
	.preview {
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.header h2 {
		margin: 0;
		font-size: 18px;
	}
	.video-container {
		background: #000;
		border-radius: 8px;
		overflow: hidden;
	}
	.video-player {
		width: 100%;
		display: block;
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
	}
	.toggle.active {
		background: #f97316;
	}
	.toggle:disabled {
		opacity: 0.5;
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
	.progress-section {
		background: #1e293b;
		border-radius: 10px;
		padding: 14px 18px;
	}
	.progress-header {
		display: flex;
		justify-content: space-between;
		font-size: 12px;
		color: #94a3b8;
		margin-bottom: 8px;
	}
	.progress-bar {
		height: 4px;
		background: #334155;
		border-radius: 2px;
	}
	.progress-fill {
		height: 4px;
		background: #f97316;
		border-radius: 2px;
		transition: width 0.3s;
	}
	.error-box {
		background: #7f1d1d;
		color: #fecaca;
		padding: 12px 14px;
		border-radius: 8px;
		font-size: 12px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.link-btn {
		background: none;
		border: none;
		color: #fca5a5;
		cursor: pointer;
		font-size: 11px;
	}
	.saved-info {
		background: #1e293b;
		border-radius: 8px;
		padding: 14px;
	}
	.saved-label {
		font-size: 11px;
		color: #64748b;
	}
	.saved-path {
		font-size: 12px;
		color: #cbd5e1;
		font-family: monospace;
		word-break: break-all;
		margin-top: 4px;
	}
	.actions {
		display: flex;
		gap: 10px;
	}
	.btn {
		flex: 1;
		padding: 12px;
		border: none;
		border-radius: 8px;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
	}
	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.btn.primary {
		background: #f97316;
		color: white;
	}
	.btn.primary:hover:not(:disabled) {
		background: #ea580c;
	}
	.btn.secondary {
		background: #334155;
		color: #94a3b8;
	}
	.btn.secondary:hover:not(:disabled) {
		background: #475569;
	}
	.drive-link {
		background: #1e293b;
		border-radius: 8px;
		padding: 14px;
	}
	.link {
		font-size: 12px;
		color: #60a5fa;
		word-break: break-all;
		margin-top: 4px;
		display: block;
	}
</style>

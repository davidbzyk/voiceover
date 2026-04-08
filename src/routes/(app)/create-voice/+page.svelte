<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState } from '$lib/state.svelte';
	import { voicebox, type VoiceboxModelStatus } from '$lib/voicebox';
	import { getRequiredModelNames } from '$lib/models';
	import { onMount } from 'svelte';

	// Wizard step (1-5)
	let step = $state(1);

	// Step 1: Prerequisites
	let healthy = $state<boolean | null>(null);
	let checkingHealth = $state(false);
	let models = $state<VoiceboxModelStatus[]>([]);
	let downloading = $state(false);
	let downloadError = $state('');
	let prerequisiteError = $state('');

	// Step 2: Create profile
	let profileName = $state('');
	let profileLanguage = $state('en');
	let creating = $state(false);
	let createError = $state('');
	let profileId = $state('');

	// Step 3: Source voice sample (YouTube or file upload)
	let sampleSource = $state<'youtube' | 'file'>('youtube');
	let youtubeUrl = $state('');
	let youtubeStart = $state('0');
	let youtubeDuration = $state(30);
	let extracting = $state(false);
	let extractError = $state('');
	let audioFile = $state<File | null>(null);
	let referenceText = $state('');
	let transcribing = $state(false);
	let uploading = $state(false);
	let uploadError = $state('');
	let uploadedAudioUrl = $state('');
	// Path to extracted audio on the sidecar filesystem (for YouTube flow)
	let extractedAudioPath = $state('');

	// Step 4: Test voice
	let testText = $state('Hello, this is a test of my cloned voice.');
	let generating = $state(false);
	let generateError = $state('');
	let generatedAudioUrl = $state('');

	const languages = [
		{ code: 'en', label: 'English' },
		{ code: 'zh', label: 'Chinese' },
		{ code: 'ja', label: 'Japanese' },
		{ code: 'ko', label: 'Korean' },
		{ code: 'de', label: 'German' },
		{ code: 'fr', label: 'French' },
		{ code: 'ru', label: 'Russian' },
		{ code: 'pt', label: 'Portuguese' },
		{ code: 'es', label: 'Spanish' },
		{ code: 'it', label: 'Italian' }
	];

	const YOUTUBE_URL_PATTERN = /^https?:\/\/(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com)\//;

	function isValidYouTubeUrl(url: string): boolean {
		return YOUTUBE_URL_PATTERN.test(url.trim());
	}

	onMount(() => {
		checkPrerequisites();
	});

	async function checkPrerequisites() {
		checkingHealth = true;
		prerequisiteError = '';
		const client = voicebox;

		try {
			healthy = await client.checkHealth();
			if (!healthy) {
				checkingHealth = false;
				return;
			}

			models = await client.getModelStatus();

			// Only check models required for the current mode
			const requiredModels = getRequiredModelNames(appState.config);
			const allDownloaded = requiredModels.every((reqName) =>
				models.some((m) => m.model_name === reqName && m.downloaded)
			);

			// Auto-advance if all required models are ready
			if (allDownloaded) {
				step = 2;
			}
		} catch (err) {
			healthy = false;
			prerequisiteError = String(err);
		}
		checkingHealth = false;
	}

	async function downloadModels() {
		downloading = true;
		downloadError = '';
		const client = voicebox;

		// Only download models required for the current mode
		const requiredModels = getRequiredModelNames(appState.config);
		const missing = models.filter(
			(m) => !m.downloaded && requiredModels.includes(m.model_name)
		);

		if (missing.length === 0) {
			step = 2;
			downloading = false;
			return;
		}

		try {
			for (const model of missing) {
				await client.downloadModel(model.model_name, (_progress, status) => {
					downloadError = status;
				});
			}
			downloadError = '';

			// Refresh model status after all downloads complete
			models = await client.getModelStatus();
			const allDownloaded = requiredModels.every((reqName) =>
				models.some((m) => m.model_name === reqName && m.downloaded)
			);
			if (allDownloaded) {
				step = 2;
			}
		} catch (err) {
			downloadError = String(err);
		}
		downloading = false;
	}

	async function createProfile() {
		creating = true;
		createError = '';
		const client = voicebox;

		try {
			const profile = await client.createProfile(profileName.trim(), profileLanguage);
			profileId = profile.id;
			step = 3;
		} catch (err) {
			createError = String(err);
		}
		creating = false;
	}

	async function extractFromYouTube() {
		if (!isValidYouTubeUrl(youtubeUrl)) {
			extractError = 'Please enter a valid YouTube URL';
			return;
		}
		extracting = true;
		extractError = '';
		try {
			const { tauriInvoke } = await import('$lib/tauri');
			const result = await tauriInvoke<{ audio_path: string; duration: number }>(
				'extract_youtube_audio',
				{ url: youtubeUrl, start: youtubeStart, duration: youtubeDuration }
			);
			extractedAudioPath = result.audio_path;
			extracting = false;

			// Auto-transcribe the extracted audio
			transcribing = true;
			const transcriptResult = await tauriInvoke<string>('sidecar_fetch', {
				path: '/transcribe-path',
				method: 'POST',
				body: JSON.stringify({ audio_path: extractedAudioPath }),
			});
			const parsed = JSON.parse(transcriptResult);
			referenceText = parsed.text || '';
		} catch (err) {
			extractError = String(err);
		}
		extracting = false;
		transcribing = false;
	}

	function handleFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files && input.files.length > 0) {
			audioFile = input.files[0];
		}
	}

	async function transcribeUploadedFile() {
		if (!audioFile) return;
		transcribing = true;
		uploadError = '';
		try {
			const client = voicebox;
			// Upload the file for transcription only
			const { tauriInvoke } = await import('$lib/tauri');
			const buffer = await audioFile.arrayBuffer();
			const fileBytes = new Uint8Array(buffer);
			const result = await tauriInvoke<string>('sidecar_upload', {
				path: '/transcribe',
				fileBytes,
				fileName: audioFile.name,
				fileField: 'file',
				fields: {}
			});
			const parsed = JSON.parse(result);
			referenceText = parsed.text || '';
		} catch (err) {
			uploadError = `Transcription failed: ${err}`;
		}
		transcribing = false;
	}

	async function uploadSample() {
		uploading = true;
		uploadError = '';
		const client = voicebox;

		try {
			if (sampleSource === 'youtube' && extractedAudioPath) {
				// YouTube flow: the audio is already on the sidecar filesystem
				// Upload it as a sample using the path
				const { tauriInvoke } = await import('$lib/tauri');
				await tauriInvoke<string>('sidecar_fetch', {
					path: `/profiles/${profileId}/samples/from-path`,
					method: 'POST',
					body: JSON.stringify({
						audio_path: extractedAudioPath,
						reference_text: referenceText.trim(),
					}),
				});
			} else if (audioFile) {
				// File upload flow
				await client.uploadSample(profileId, audioFile, referenceText.trim());
				uploadedAudioUrl = URL.createObjectURL(audioFile);
			}
			step = 4;
		} catch (err) {
			uploadError = String(err);
		}
		uploading = false;
	}

	async function testGenerate() {
		generating = true;
		generateError = '';
		if (generatedAudioUrl) URL.revokeObjectURL(generatedAudioUrl);
		generatedAudioUrl = '';
		const client = voicebox;

		try {
			const gen = await client.testGenerate(profileId, testText.trim());
			await client.pollGenerationStatus(gen.id);
			generatedAudioUrl = await client.getAudioUrl(gen.id);
		} catch (err) {
			generateError = String(err);
		}
		generating = false;
	}

	async function finishWizard() {
		appState.config.local_voice_profile_id = profileId;
		appState.config.provider = 'local';
		await appState.saveConfig();
		goto('/settings');
	}

	function goBack() {
		goto('/settings');
	}
</script>

<div class="wizard">
	<div class="header">
		<button class="back-btn" onclick={goBack}>← Back</button>
		<h2>Create Voice</h2>
	</div>

	<!-- Step indicator -->
	<div class="steps">
		{#each [1, 2, 3, 4, 5] as s}
			<div class="step-dot" class:active={step === s} class:done={step > s}></div>
		{/each}
	</div>

	<!-- Step 1: Prerequisites -->
	{#if step === 1}
		<div class="section">
			<div class="section-title">Prerequisites</div>
			<div class="card">
				{#if checkingHealth}
					<div class="status-row">
						<span class="status-dot connecting"></span>
						<span>Checking Voicebox connection...</span>
					</div>
				{:else if healthy === false}
					<div class="status-row">
						<span class="status-dot disconnected"></span>
						<span>TTS engine is not running</span>
					</div>
					<div class="hint-text">
						The local TTS sidecar failed to start. Try restarting the app.
					</div>
					{#if prerequisiteError}
						<div class="status invalid">{prerequisiteError}</div>
					{/if}
					<button class="small-btn accent" onclick={checkPrerequisites}>
						Retry Connection
					</button>
				{:else if healthy === true}
					<div class="status-row">
						<span class="status-dot connected"></span>
						<span>TTS engine ready</span>
					</div>

					<!-- Show status of required models only -->
					{@const requiredModelNames = [
						appState.config.whisper_model,
						...(appState.config.local_tts_mode === 'vc' ? ['cosyvoice3-0.5B'] : ['qwen-tts-1.7B'])
					]}
					{#each models.filter((m) => requiredModelNames.includes(m.model_name)) as model}
						<div class="status-row">
							<span class="status-dot" class:connected={model.downloaded}></span>
							<span>{model.display_name}</span>
						</div>
					{/each}

					{@const missing = models.filter((m) => !m.downloaded && requiredModelNames.includes(m.model_name))}
					{#if missing.length > 0}
						<div class="hint-text">
							{#if missing.length === 1}
								{missing[0].display_name} needs to be downloaded.
							{:else}
								{@const names = missing.map((m) => m.display_name)}
								{names.slice(0, -1).join(', ')} and {names[names.length - 1]} need to be downloaded (~5GB total).
							{/if}
						</div>
						<button
							class="small-btn accent"
							onclick={downloadModels}
							disabled={downloading}
						>
							{downloading ? 'Downloading...' : `Download ${missing.length === 1 ? missing[0].display_name : 'Models'}`}
						</button>
						{#if downloading}
							<div class="progress-section">
								<div class="progress-bar">
									<div class="progress-fill indeterminate"></div>
								</div>
								<div class="hint-text">This may take several minutes depending on your connection.</div>
							</div>
						{/if}
						{#if downloadError}
							<div class="status invalid">{downloadError}</div>
						{/if}
					{:else}
						<div class="status-row">
							<span class="status-dot connected"></span>
							<span>All models ready</span>
						</div>
						<button class="small-btn accent" onclick={() => (step = 2)}>
							Continue
						</button>
					{/if}
				{/if}
			</div>
		</div>
	{/if}

	<!-- Step 2: Create Profile -->
	{#if step === 2}
		<div class="section">
			<div class="section-title">Create Voice Profile</div>
			<div class="card">
				<label class="field-label" for="profile-name">Name</label>
				<input
					id="profile-name"
					bind:value={profileName}
					placeholder="My Voice"
					class="input"
				/>

				<label class="field-label" for="profile-language">Language</label>
				<select
					id="profile-language"
					bind:value={profileLanguage}
					class="input"
				>
					{#each languages as lang}
						<option value={lang.code}>{lang.label}</option>
					{/each}
				</select>

				{#if createError}
					<div class="status invalid">{createError}</div>
				{/if}

				<button
					class="small-btn accent"
					onclick={createProfile}
					disabled={!profileName.trim() || creating}
				>
					{creating ? 'Creating...' : 'Create'}
				</button>
			</div>
		</div>
	{/if}

	<!-- Step 3: Source Voice Sample -->
	{#if step === 3}
		<div class="section">
			<div class="section-title">Voice Sample</div>
			<div class="card">
				<div class="hint-text">
					Provide a clean 5-30 second audio clip of the voice to clone.
				</div>

				<!-- Source selector -->
				<div class="provider-toggle">
					<button
						class="provider-btn"
						class:active={sampleSource === 'youtube'}
						onclick={() => (sampleSource = 'youtube')}
					>
						YouTube URL
					</button>
					<button
						class="provider-btn"
						class:active={sampleSource === 'file'}
						onclick={() => (sampleSource = 'file')}
					>
						Upload File
					</button>
				</div>

				{#if sampleSource === 'youtube'}
					<!-- YouTube extraction -->
					<label class="field-label" for="youtube-url">YouTube URL</label>
					<input
						id="youtube-url"
						bind:value={youtubeUrl}
						placeholder="https://www.youtube.com/watch?v=..."
						class="input"
					/>

					<div class="inline-fields">
						<div>
							<label class="field-label" for="yt-start">Start time</label>
							<input id="yt-start" bind:value={youtubeStart} placeholder="0:00" class="input small" />
						</div>
						<div>
							<label class="field-label" for="yt-duration">Duration (s)</label>
							<input id="yt-duration" type="number" bind:value={youtubeDuration} min="5" max="30" class="input small" />
						</div>
					</div>

					<button
						class="small-btn accent"
						onclick={extractFromYouTube}
						disabled={!youtubeUrl.trim() || !isValidYouTubeUrl(youtubeUrl) || extracting}
					>
						{extracting ? 'Extracting...' : 'Extract Audio'}
					</button>

					{#if extracting}
						<div class="progress-section">
							<div class="progress-bar"><div class="progress-fill indeterminate"></div></div>
							<div class="hint-text">Downloading and extracting audio...</div>
						</div>
					{/if}

					{#if extractError}
						<div class="status invalid">{extractError}</div>
					{/if}
				{:else}
					<!-- File upload -->
					<label class="field-label" for="audio-file">Audio File (MP3, WAV, M4A)</label>
					<input
						id="audio-file"
						type="file"
						accept="audio/*"
						onchange={handleFileSelect}
						class="input file-input"
					/>

					{#if audioFile}
						<button
							class="small-btn"
							onclick={transcribeUploadedFile}
							disabled={transcribing}
						>
							{transcribing ? 'Transcribing...' : 'Auto-Transcribe'}
						</button>
					{/if}
				{/if}

				{#if transcribing}
					<div class="progress-section">
						<div class="progress-bar"><div class="progress-fill indeterminate"></div></div>
						<div class="hint-text">Transcribing audio with Whisper...</div>
					</div>
				{/if}

				<!-- Transcript (editable, shown after extraction/transcription or manual entry) -->
				{#if extractedAudioPath || audioFile}
					<label class="field-label" for="reference-text">Transcript (edit if needed)</label>
					<textarea
						id="reference-text"
						bind:value={referenceText}
						placeholder="The transcript will appear here after extraction, or type it manually..."
						class="input textarea"
						rows="3"
					></textarea>

					{#if uploadError}
						<div class="status invalid">{uploadError}</div>
					{/if}

					<button
						class="small-btn accent"
						onclick={uploadSample}
						disabled={!referenceText.trim() || uploading}
					>
						{uploading ? 'Saving...' : 'Save Sample & Continue'}
					</button>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Step 4: Test Voice -->
	{#if step === 4}
		<div class="section">
			<div class="section-title">Test Your Voice</div>
			<div class="card">
				<label class="field-label" for="test-text">Text to speak</label>
				<textarea
					id="test-text"
					bind:value={testText}
					class="input textarea"
					rows="2"
				></textarea>

				{#if generateError}
					<div class="status invalid">{generateError}</div>
				{/if}

				<div class="button-row">
					<button
						class="small-btn accent"
						onclick={testGenerate}
						disabled={!testText.trim() || generating}
					>
						{generating ? 'Generating...' : 'Generate Test'}
					</button>
				</div>

				{#if generating}
					<div class="progress-section">
						<div class="progress-bar">
							<div class="progress-fill indeterminate"></div>
						</div>
						<div class="hint-text">Generating speech...</div>
					</div>
				{/if}

				{#if generatedAudioUrl}
					<audio controls src={generatedAudioUrl} class="audio-player">
						<track kind="captions" />
					</audio>

					<div class="button-row">
						<button class="small-btn" onclick={testGenerate} disabled={generating}>
							Try Again
						</button>
						<button class="small-btn" onclick={() => { generatedAudioUrl = ''; step = 3; }}>
							Upload Another Sample
						</button>
						<button class="small-btn accent" onclick={() => (step = 5)}>
							Looks Good
						</button>
					</div>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Step 5: Done -->
	{#if step === 5}
		<div class="section">
			<div class="section-title">Done</div>
			<div class="card done-card">
				<div class="done-message">Your voice is ready!</div>
				<div class="hint-text">
					Your new voice profile has been set as the active local voice
					and the provider has been switched to Local.
				</div>
				<button class="small-btn accent" onclick={finishWizard}>
					Go to Settings
				</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.wizard {
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
		max-width: 480px;
	}

	/* Step indicator dots */
	.steps {
		display: flex;
		gap: 8px;
		justify-content: center;
	}
	.step-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: #334155;
		transition: all 0.2s;
	}
	.step-dot.active {
		background: #f97316;
		transform: scale(1.2);
	}
	.step-dot.done {
		background: #22c55e;
	}
	.textarea {
		resize: vertical;
		min-height: 60px;
		font-family: inherit;
	}
	.file-input {
		padding: 6px;
	}
	.file-input::file-selector-button {
		background: #334155;
		border: none;
		color: #94a3b8;
		padding: 4px 10px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 11px;
		margin-right: 8px;
	}
	.file-input::file-selector-button:hover {
		background: #475569;
	}

	/* Status rows */
	.status-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
		color: #cbd5e1;
	}
	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #475569;
		flex-shrink: 0;
	}
	.status-dot.connected {
		background: #22c55e;
	}
	.status-dot.disconnected {
		background: #ef4444;
	}
	.status-dot.connecting {
		background: #f59e0b;
		animation: pulse 1s infinite;
	}
	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.4; }
	}

	/* Progress */
	.progress-section {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.progress-bar {
		height: 4px;
		background: #334155;
		border-radius: 2px;
		overflow: hidden;
	}
	.progress-fill {
		height: 4px;
		background: #f97316;
		border-radius: 2px;
	}
	.progress-fill.indeterminate {
		width: 40%;
		animation: indeterminate 1.5s infinite ease-in-out;
	}
	@keyframes indeterminate {
		0% { transform: translateX(-100%); }
		100% { transform: translateX(350%); }
	}

	/* Audio player */
	.audio-player {
		width: 100%;
		height: 36px;
		border-radius: 6px;
	}

	/* Button row */
	.button-row {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	/* Done */
	.done-card {
		align-items: center;
		text-align: center;
		padding: 24px 14px;
	}
	.done-message {
		font-size: 16px;
		font-weight: 600;
		color: #22c55e;
	}
	.inline-fields {
		display: flex;
		gap: 10px;
	}
	.inline-fields > div {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
</style>

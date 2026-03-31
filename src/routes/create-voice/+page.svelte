<script lang="ts">
	import { goto } from '$app/navigation';
	import { appState } from '$lib/state.svelte';
	import { VoiceboxClient, type VoiceboxModelStatus } from '$lib/voicebox';
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

	// Step 3: Upload reference audio
	let audioFile = $state<File | null>(null);
	let referenceText = $state('');
	let uploading = $state(false);
	let uploadError = $state('');
	let uploadedAudioUrl = $state('');

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

	function getClient(): VoiceboxClient {
		return new VoiceboxClient(appState.config.local_endpoint);
	}

	onMount(() => {
		checkPrerequisites();
	});

	async function checkPrerequisites() {
		checkingHealth = true;
		prerequisiteError = '';
		const client = getClient();

		try {
			healthy = await client.checkHealth();
			if (!healthy) {
				checkingHealth = false;
				return;
			}

			models = await client.getModelStatus();
			const qwen = models.find(
				(m) => m.model_name.toLowerCase().includes('qwen')
			);

			// Auto-advance if Qwen is ready
			if (qwen?.downloaded) {
				step = 2;
			}
		} catch (err) {
			healthy = false;
			prerequisiteError = String(err);
		}
		checkingHealth = false;
	}

	async function downloadQwen() {
		downloading = true;
		downloadError = '';
		const client = getClient();
		const qwen = models.find(
			(m) => m.model_name.toLowerCase().includes('qwen')
		);
		if (!qwen) {
			downloadError = 'Qwen model not found in model list.';
			downloading = false;
			return;
		}

		try {
			await client.downloadModel(qwen.model_name);
			// Poll model status until downloaded
			let attempts = 0;
			while (attempts < 600) {
				await new Promise((r) => setTimeout(r, 3000));
				const updated = await client.getModelStatus();
				const updatedQwen = updated.find(
					(m) => m.model_name.toLowerCase().includes('qwen')
				);
				if (updatedQwen?.downloaded) {
					models = updated;
					step = 2;
					downloading = false;
					return;
				}
				attempts++;
			}
			downloadError = 'Download timed out. Check the Voicebox server.';
		} catch (err) {
			downloadError = String(err);
		}
		downloading = false;
	}

	async function createProfile() {
		creating = true;
		createError = '';
		const client = getClient();

		try {
			const profile = await client.createProfile(profileName.trim(), profileLanguage);
			profileId = profile.id;
			step = 3;
		} catch (err) {
			createError = String(err);
		}
		creating = false;
	}

	function handleFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files && input.files.length > 0) {
			audioFile = input.files[0];
		}
	}

	async function uploadSample() {
		if (!audioFile) return;
		uploading = true;
		uploadError = '';
		const client = getClient();

		try {
			await client.uploadSample(profileId, audioFile, referenceText.trim());
			uploadedAudioUrl = URL.createObjectURL(audioFile);
			step = 4;
		} catch (err) {
			uploadError = String(err);
		}
		uploading = false;
	}

	async function testGenerate() {
		generating = true;
		generateError = '';
		generatedAudioUrl = '';
		const client = getClient();

		try {
			const gen = await client.testGenerate(profileId, testText.trim());
			await client.pollGenerationStatus(gen.id);
			generatedAudioUrl = client.getAudioUrl(gen.id);
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
						<span>Voicebox is not running</span>
					</div>
					<div class="hint-text">
						Start Voicebox to continue. Make sure it is running at:
					</div>
					<input
						bind:value={appState.config.local_endpoint}
						placeholder="http://localhost:17493"
						class="input"
					/>
					{#if prerequisiteError}
						<div class="status invalid">{prerequisiteError}</div>
					{/if}
					<button class="small-btn accent" onclick={checkPrerequisites}>
						Retry Connection
					</button>
				{:else if healthy === true}
					<div class="status-row">
						<span class="status-dot connected"></span>
						<span>Voicebox connected</span>
					</div>

					{@const qwen = models.find((m) => m.model_name.toLowerCase().includes('qwen'))}
					{#if qwen && !qwen.downloaded}
						<div class="hint-text">
							The Qwen3-TTS model (~3.4GB) needs to be downloaded before you can create a voice.
						</div>
						<button
							class="small-btn accent"
							onclick={downloadQwen}
							disabled={downloading}
						>
							{downloading ? 'Downloading...' : 'Download Qwen3-TTS'}
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
					{:else if qwen && qwen.downloaded}
						<div class="status-row">
							<span class="status-dot connected"></span>
							<span>Qwen3-TTS model ready</span>
						</div>
						<button class="small-btn accent" onclick={() => (step = 2)}>
							Continue
						</button>
					{:else}
						<div class="hint-text">
							No Qwen model found. Check your Voicebox installation.
						</div>
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

	<!-- Step 3: Upload Reference Audio -->
	{#if step === 3}
		<div class="section">
			<div class="section-title">Upload Reference Audio</div>
			<div class="card">
				<div class="hint-text">
					Use a clean 5-30 second recording for best results.
				</div>

				<label class="field-label" for="audio-file">Audio File</label>
				<input
					id="audio-file"
					type="file"
					accept="audio/*"
					onchange={handleFileSelect}
					class="input file-input"
				/>

				<label class="field-label" for="reference-text">Transcript of the Audio</label>
				<textarea
					id="reference-text"
					bind:value={referenceText}
					placeholder="Type the exact words spoken in the recording..."
					class="input textarea"
					rows="3"
				></textarea>

				{#if uploadError}
					<div class="status invalid">{uploadError}</div>
				{/if}

				<button
					class="small-btn accent"
					onclick={uploadSample}
					disabled={!audioFile || !referenceText.trim() || uploading}
				>
					{uploading ? 'Uploading...' : 'Upload'}
				</button>

				{#if uploadedAudioUrl}
					<audio controls src={uploadedAudioUrl} class="audio-player">
						<track kind="captions" />
					</audio>
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
	.header {
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.header h2 {
		margin: 0;
		font-size: 18px;
	}
	.back-btn {
		background: #334155;
		border: none;
		color: #94a3b8;
		padding: 6px 12px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 13px;
	}
	.back-btn:hover {
		background: #475569;
		color: #f1f5f9;
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

	.section {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.section-title {
		font-size: 13px;
		font-weight: 600;
	}
	.card {
		background: #1e293b;
		border-radius: 8px;
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.field-label {
		font-size: 11px;
		color: #64748b;
	}
	.input {
		background: #0f172a;
		border: 1px solid #334155;
		border-radius: 6px;
		padding: 8px 12px;
		color: #cbd5e1;
		font-size: 12px;
		outline: none;
		width: 100%;
	}
	.input:focus {
		border-color: #f97316;
	}
	select.input {
		appearance: none;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2364748b' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 10px center;
		padding-right: 28px;
		cursor: pointer;
	}
	select.input option {
		background: #0f172a;
		color: #cbd5e1;
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
	.small-btn {
		background: #334155;
		border: none;
		color: #94a3b8;
		padding: 6px 10px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 12px;
		white-space: nowrap;
	}
	.small-btn:hover {
		background: #475569;
	}
	.small-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.small-btn.accent {
		background: #f97316;
		color: white;
	}
	.small-btn.accent:disabled {
		opacity: 0.4;
	}
	.status {
		font-size: 11px;
	}
	.status.invalid {
		color: #ef4444;
	}
	.hint-text {
		font-size: 11px;
		color: #64748b;
		line-height: 1.4;
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
</style>

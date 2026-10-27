<script lang="ts">
	import { onMount } from 'svelte';
	import { appState } from '$lib/state.svelte';
	import {
		buildVoiceOptions,
		choiceKey,
		defaultVoiceChoice,
		pickVoice,
		shouldLoadLocalVoices,
		type VoiceChoice
	} from '$lib/conversion';
	import { localVoices } from '$lib/localVoice.svelte';
	import EnginePicker from '$lib/EnginePicker.svelte';

	let {
		value = $bindable<VoiceChoice | null>(null),
		disabled = false
	}: { value?: VoiceChoice | null; disabled?: boolean } = $props();

	const options = $derived(buildVoiceOptions(appState.config, localVoices.profiles));
	const eleven = $derived(options.filter((o) => o.provider === 'elevenlabs'));
	const local = $derived(options.filter((o) => o.provider === 'local'));

	onMount(() => {
		value ??= defaultVoiceChoice(appState.config);
		if (shouldLoadLocalVoices(appState.config)) localVoices.refresh();
	});
</script>

<div class="voice-picker-row">
	<select
		class="voice-picker"
		aria-label="Voice"
		{disabled}
		value={value ? choiceKey(value) : ''}
		onchange={(e) => (value = pickVoice((e.target as HTMLSelectElement).value, value, appState.config))}
	>
		{#if !value}
			<option value="" disabled>Choose a voice</option>
		{/if}
		{#if eleven.length > 0}
			<optgroup label="ElevenLabs">
				{#each eleven as option (choiceKey(option))}
					<option value={choiceKey(option)}>{option.name}</option>
				{/each}
			</optgroup>
		{/if}
		{#if local.length > 0}
			<optgroup label="Local">
				{#each local as option (choiceKey(option))}
					<option value={choiceKey(option)}>{option.name}</option>
				{/each}
			</optgroup>
		{/if}
	</select>
	{#if value?.provider === 'local'}
		<EnginePicker
			{disabled}
			value={value.engine ?? null}
			onchange={(engine) => value && (value = { ...value, engine })}
		/>
	{/if}
</div>

<style>
	.voice-picker-row {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		align-items: center;
		min-width: 0;
	}
	.voice-picker {
		background: #0f172a;
		color: #e2e8f0;
		border: 1px solid #334155;
		border-radius: 6px;
		padding: 6px 8px;
		font-size: 12px;
		min-width: 0;
		max-width: 100%;
	}
	.voice-picker:disabled {
		opacity: 0.5;
	}
</style>

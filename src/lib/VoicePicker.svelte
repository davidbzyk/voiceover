<script lang="ts">
	import { onMount } from 'svelte';
	import { appState } from '$lib/state.svelte';
	import {
		buildVoiceOptions,
		choiceKey,
		defaultVoiceChoice,
		loadLocalVoices,
		parseChoiceKey,
		type VoiceChoice
	} from '$lib/conversion';

	let {
		value = $bindable<VoiceChoice | null>(null),
		disabled = false
	}: { value?: VoiceChoice | null; disabled?: boolean } = $props();

	let localVoices = $state<{ id: string; name: string }[]>([]);
	const options = $derived(buildVoiceOptions(appState.config, localVoices));
	const eleven = $derived(options.filter((o) => o.provider === 'elevenlabs'));
	const local = $derived(options.filter((o) => o.provider === 'local'));

	onMount(async () => {
		localVoices = await loadLocalVoices();
		value ??= defaultVoiceChoice(appState.config);
	});
</script>

<select
	class="voice-picker"
	aria-label="Voice"
	{disabled}
	value={value ? choiceKey(value) : ''}
	onchange={(e) => (value = parseChoiceKey((e.target as HTMLSelectElement).value))}
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
		<optgroup label="Local (CosyVoice)">
			{#each local as option (choiceKey(option))}
				<option value={choiceKey(option)}>{option.name}</option>
			{/each}
		</optgroup>
	{/if}
</select>

<style>
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

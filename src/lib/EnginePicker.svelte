<script lang="ts">
	import { engineOptions, localVoices } from '$lib/localVoice.svelte';

	let {
		value = $bindable<string | null>(null),
		textOnly = false,
		disabled = false,
		onchange
	}: {
		value?: string | null;
		/** Only engines that read text: Create Voice speaks a test sentence. */
		textOnly?: boolean;
		disabled?: boolean;
		/** Called after the user picks an engine. */
		onchange?: (engine: string) => void;
	} = $props();

	const engines = $derived(engineOptions(localVoices.models, textOnly));
	const speech = $derived(engines.filter((e) => e.kind === 'speech-to-speech'));
	const text = $derived(engines.filter((e) => e.kind === 'text-to-speech'));
	const noneDownloaded = $derived(localVoices.loaded && !engines.some((e) => e.downloaded));
	/** A saved pick whose weights were deleted since: converting with it would download them first. */
	const pickedMissing = $derived(engines.find((e) => e.key === value && !e.downloaded));
</script>

<select
	class="engine-picker"
	aria-label="Engine"
	{disabled}
	value={value ?? ''}
	onchange={(e) => {
		value = (e.target as HTMLSelectElement).value;
		onchange?.(value);
	}}
>
	{#if !value}
		<option value="" disabled>{localVoices.loaded ? 'Choose an engine' : 'Loading engines...'}</option>
	{/if}
	{#if speech.length > 0}
		<optgroup label="Speech to speech">
			{#each speech as engine (engine.key)}
				<option value={engine.key} disabled={!engine.downloaded}>
					{engine.name}{engine.downloaded ? '' : ' (not downloaded)'}
				</option>
			{/each}
		</optgroup>
	{/if}
	{#if text.length > 0}
		<optgroup label="Text to speech">
			{#each text as engine (engine.key)}
				<option value={engine.key} disabled={!engine.downloaded}>
					{engine.name}{engine.downloaded ? '' : ' (not downloaded)'}
				</option>
			{/each}
		</optgroup>
	{/if}
</select>
{#if noneDownloaded}
	<a class="engine-hint" href="/models">Download an engine on the Models page</a>
{:else if pickedMissing}
	<a class="engine-hint" href="/models">{pickedMissing.name} is not downloaded: get it on the Models page</a>
{/if}

<style>
	.engine-picker {
		background: #0f172a;
		color: #e2e8f0;
		border: 1px solid #334155;
		border-radius: 6px;
		padding: 6px 8px;
		font-size: 12px;
		min-width: 0;
		max-width: 100%;
	}
	.engine-picker:disabled {
		opacity: 0.5;
	}
	.engine-hint {
		font-size: 11px;
		color: #60a5fa;
	}
</style>

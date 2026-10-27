/**
 * Local voice profiles and engines from the sidecar, shared by every screen that shows or picks them,
 * so a profile or engine picked on one screen shows on the others.
 */
import type { AppConfig } from './state.svelte';
import type { VoiceChoice } from './conversion';
import { voicebox, type VoiceboxModelStatus, type VoiceboxProfile } from './voicebox';

/** One engine as the pickers list it. */
export interface EngineOption {
	key: string;
	name: string;
	/** Speech-to-speech engines convert the speech itself; text-to-speech engines speak from a transcript. */
	kind: 'speech-to-speech' | 'text-to-speech';
	downloaded: boolean;
}

const KIND_OF_CATEGORY = { 'voice-conversion': 'speech-to-speech', tts: 'text-to-speech' } as const;

/**
 * The engines that can replace a voice, speech-to-speech first, from the sidecar's model rows.
 * Engines not downloaded yet stay listed so the pickers can show them greyed; `textOnly` keeps those that read text.
 */
export function engineOptions(models: VoiceboxModelStatus[], textOnly = false): EngineOption[] {
	const options: EngineOption[] = [];
	for (const m of models) {
		if (m.category === 'transcription' || (textOnly && m.category !== 'tts')) continue;
		options.push({ key: m.model_name, name: m.display_name, kind: KIND_OF_CATEGORY[m.category], downloaded: m.downloaded });
	}
	return options.sort((a, b) => Number(a.kind === 'text-to-speech') - Number(b.kind === 'text-to-speech'));
}

/** "Voice · Engine" for a choice, e.g. "Michael Jackson · Qwen3-TTS 1.7B" or "Adam · ElevenLabs". */
export function describeChoice(
	choice: VoiceChoice,
	config: Pick<AppConfig, 'voices'>,
	profiles: { id: string; name: string }[],
	engines: EngineOption[]
): string {
	if (choice.provider === 'elevenlabs') {
		return `${config.voices.find((v) => v.id === choice.voiceId)?.name ?? 'No voice'} · ElevenLabs`;
	}
	const profile = profiles.find((p) => p.id === choice.voiceId)?.name ?? 'No profile';
	return `${profile} · ${engines.find((e) => e.key === choice.engine)?.name ?? 'No engine'}`;
}

/** The voice and engine Settings would convert with, for labels; ids are empty when nothing is picked. */
export function settingsChoice(
	config: Pick<AppConfig, 'provider' | 'voices' | 'local_voice_profile_id' | 'local_engine'>
): VoiceChoice {
	if (config.provider === 'local') {
		return { provider: 'local', voiceId: config.local_voice_profile_id, engine: config.local_engine };
	}
	const voice = config.voices.find((v) => v.is_default) ?? config.voices[0];
	return { provider: 'elevenlabs', voiceId: voice?.id ?? '' };
}

class LocalVoices {
	profiles = $state<VoiceboxProfile[]>([]);
	models = $state<VoiceboxModelStatus[]>([]);
	/** True once a refresh has succeeded. */
	loaded = $state(false);
	error = $state('');
	engines = $derived(engineOptions(this.models));
	#inFlight: Promise<void> | null = null;

	/** Fetch profiles and engines from the sidecar, starting it if needed; overlapping calls share one fetch. */
	refresh(): Promise<void> {
		this.#inFlight ??= (async () => {
			try {
				// One after the other: each command starts the sidecar if it is not running.
				const profiles = await voicebox.listProfiles();
				const models = await voicebox.getModelStatus();
				this.profiles = profiles;
				this.models = models;
				this.loaded = true;
				this.error = '';
			} catch (err) {
				this.error = err instanceof Error ? err.message : String(err);
			} finally {
				this.#inFlight = null;
			}
		})();
		return this.#inFlight;
	}
}

export const localVoices = new LocalVoices();

/**
 * Voice choices and the conversion commands shared by the Preview page and Library cards.
 */
import type { AppConfig } from './state.svelte';

export type VoiceProvider = 'elevenlabs' | 'local';

/** The voice a conversion should use; matches the Rust `VoiceChoice`. */
export interface VoiceChoice {
	provider: VoiceProvider;
	voiceId: string;
	/** Sidecar registry key of the local engine; unset for ElevenLabs, and for a local voice nothing picks one yet. */
	engine?: string | null;
}

/** One entry in the voice picker. */
export interface VoiceOption extends VoiceChoice {
	name: string;
}

/** Stable string form of a choice, for <select> values. */
export function choiceKey(choice: VoiceChoice): string {
	return `${choice.provider}:${choice.voiceId}`;
}

/** Inverse of choiceKey. */
export function parseChoiceKey(key: string): VoiceChoice {
	const i = key.indexOf(':');
	return { provider: key.slice(0, i) as VoiceProvider, voiceId: key.slice(i + 1) };
}

/** Every voice the user can convert to: ElevenLabs voices (when a key is set) and local profiles. */
export function buildVoiceOptions(
	config: Pick<AppConfig, 'voices' | 'elevenlabs_api_key'>,
	localVoices: { id: string; name: string }[]
): VoiceOption[] {
	const eleven = config.elevenlabs_api_key
		? config.voices.map((v) => ({ provider: 'elevenlabs' as const, voiceId: v.id, name: v.name }))
		: [];
	const local = localVoices.map((v) => ({ provider: 'local' as const, voiceId: v.id, name: v.name }));
	return [...eleven, ...local];
}

type SavedVoiceConfig = Pick<AppConfig, 'provider' | 'voices' | 'local_voice_profile_id' | 'local_engine'>;

/** The voice and engine saved in Settings for the active provider; the voice id is empty when none is saved. */
export function savedVoiceChoice(config: SavedVoiceConfig): VoiceChoice {
	if (config.provider === 'local') {
		return { provider: 'local', voiceId: config.local_voice_profile_id, engine: config.local_engine || null };
	}
	const voice = config.voices.find((v) => v.is_default) ?? config.voices[0];
	return { provider: 'elevenlabs', voiceId: voice?.id ?? '' };
}

/** The Settings default for the active provider, or null when none is configured. */
export function defaultVoiceChoice(config: SavedVoiceConfig): VoiceChoice | null {
	const choice = savedVoiceChoice(config);
	return choice.voiceId ? choice : null;
}

/** Whether to ask the local engine for voices; asking starts it, so ElevenLabs-only setups skip it. */
export function shouldLoadLocalVoices(
	config: Pick<AppConfig, 'provider' | 'local_voice_profile_id'>
): boolean {
	return config.provider === 'local' || !!config.local_voice_profile_id;
}

/** Whether a choice can be converted to: a voice, and for a local voice an engine too. */
export function choiceReady(choice: VoiceChoice | null): choice is VoiceChoice {
	return !!choice && !!choice.voiceId && (choice.provider !== 'local' || !!choice.engine);
}

/** The choice after picking `key` in the voice select: a local voice keeps the engine already picked, else the saved one. */
export function pickVoice(
	key: string,
	current: VoiceChoice | null,
	config: Pick<AppConfig, 'local_engine'>
): VoiceChoice {
	const { provider, voiceId } = parseChoiceKey(key);
	if (provider === 'elevenlabs') return { provider, voiceId };
	const engine = (current?.provider === 'local' ? current.engine : null) || config.local_engine || null;
	return { provider, voiceId, engine };
}

type PipelineEvent =
	| { event: 'progress'; data: { stage: string; percent: number } }
	| { event: 'complete'; data: { outputPath: string } }
	| { event: 'error'; data: { message: string } };

/** Each conversion command's arguments, matching its Rust signature. */
export interface ConversionArgs {
	process_recording: { recordingPath: string; voiceReplacement: boolean; voiceChoice: VoiceChoice | null };
	reconvert_recording: { path: string; voiceChoice: VoiceChoice | null };
}

/** Run `process_recording` or `reconvert_recording`, reporting progress; resolves to the output path. */
export async function runConversion<C extends keyof ConversionArgs>(
	command: C,
	args: ConversionArgs[C],
	onProgress: (stage: string, percent: number) => void
): Promise<string> {
	const { invoke, Channel } = await import('@tauri-apps/api/core');
	const onEvent = new Channel<PipelineEvent>();
	onEvent.onmessage = (msg) => {
		if (msg.event === 'progress') onProgress(msg.data.stage, msg.data.percent);
	};
	return invoke<string>(command, { ...args, onEvent });
}

/** Stop the conversion in progress; it fails with "Conversion cancelled". */
export async function cancelConversion(): Promise<void> {
	const { invoke } = await import('@tauri-apps/api/core');
	await invoke('cancel_conversion');
}

/** Revoke `url` if it is a blob URL this page made; `shared` is one another owner still uses. */
export function releaseObjectUrl(url: string, shared: string | null): void {
	if (url.startsWith('blob:') && url !== shared) URL.revokeObjectURL(url);
}

/** Read a saved file into a playable object URL. */
export async function fileObjectUrl(path: string, type: string): Promise<string> {
	const { invoke } = await import('@tauri-apps/api/core');
	const bytes = await invoke<number[]>('read_file_bytes', { path });
	return URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type }));
}

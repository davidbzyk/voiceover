/**
 * Shared model utilities used across settings, models, and create-voice pages.
 */

/** Returns the model names required for the current TTS configuration. */
export function getRequiredModelNames(config: {
	whisper_model: string;
	local_tts_mode: string;
}): string[] {
	const required = [config.whisper_model];
	if (config.local_tts_mode === 'vc') {
		required.push('cosyvoice3-0.5B');
	} else {
		required.push('qwen-tts-1.7B');
	}
	return required;
}

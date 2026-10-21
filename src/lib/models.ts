/**
 * Shared model utilities used across settings, models, and create-voice pages.
 */

/** What the models are needed for: replacing a recording's voice, or creating a voice profile. */
export type ModelPurpose = 'replace' | 'create-voice';

/**
 * Returns the model names a purpose needs. Replacement is speech-to-speech through CosyVoice;
 * creating a voice also speaks a test sentence, which Qwen generates from text.
 */
export function getRequiredModelNames(
	config: { whisper_model: string },
	purpose: ModelPurpose = 'replace'
): string[] {
	return [config.whisper_model, purpose === 'replace' ? 'cosyvoice3-0.5B' : 'qwen-tts-1.7B'];
}

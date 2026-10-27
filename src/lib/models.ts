/**
 * Shared model utilities used across settings, models, and create-voice pages.
 */

/**
 * The models a task needs: the chosen Whisper model, which transcribes voice samples and recordings,
 * plus `engine` (a sidecar registry key) when one has been picked.
 */
export function getRequiredModelNames(config: { whisper_model: string }, engine?: string | null): string[] {
	return engine ? [config.whisper_model, engine] : [config.whisper_model];
}

/**
 * Simple logger for VoiceOver — logs to browser console with prefixed categories.
 * Visible in F12 → Console. Filter by "[VO:" to see only VoiceOver logs.
 */

type LogLevel = 'info' | 'warn' | 'error' | 'debug';

const COLORS: Record<LogLevel, string> = {
	debug: 'color: #64748b',
	info: 'color: #60a5fa',
	warn: 'color: #f59e0b',
	error: 'color: #ef4444'
};

function log(level: LogLevel, category: string, message: string, data?: unknown) {
	const timestamp = new Date().toISOString().slice(11, 23);
	const prefix = `%c[VO:${category}]`;
	const line = `${timestamp} ${message}`;

	if (data !== undefined) {
		console[level](prefix, COLORS[level], line, data);
	} else {
		console[level](prefix, COLORS[level], line);
	}
}

export const logger = {
	// Config
	configLoaded: (source: string) => log('info', 'config', `Loaded from ${source}`),
	configSaved: (source: string) => log('info', 'config', `Saved to ${source}`),

	// Recording
	recordingStart: (mode: string) => log('info', 'record', `Starting capture: ${mode}`),
	recordingChunk: (index: number, size: number) =>
		log('debug', 'record', `Chunk ${index}: ${(size / 1024).toFixed(1)}KB`),
	recordingStop: (duration: number) =>
		log('info', 'record', `Stopped after ${duration}s`),
	recordingCancel: () => log('warn', 'record', 'Recording cancelled'),

	// ElevenLabs
	elevenLabsTest: (masked: string) =>
		log('info', 'elevenlabs', `Testing API key: ${masked}`),
	elevenLabsTestResult: (valid: boolean) =>
		log(valid ? 'info' : 'warn', 'elevenlabs', `API key ${valid ? 'valid' : 'invalid'}`),
	elevenLabsS2S: (voiceId: string) =>
		log('info', 'elevenlabs', `Speech-to-Speech: voice=${voiceId}`),
	elevenLabsS2SDone: (durationMs: number) =>
		log('info', 'elevenlabs', `S2S complete in ${(durationMs / 1000).toFixed(1)}s`),

	// Pipeline
	pipelineStart: (voiceReplacement: boolean) =>
		log('info', 'pipeline', `Processing: voiceReplacement=${voiceReplacement}`),
	pipelineStage: (stage: string, percent: number) =>
		log('info', 'pipeline', `${stage} (${percent.toFixed(0)}%)`),
	pipelineComplete: (outputPath: string) =>
		log('info', 'pipeline', `Complete: ${outputPath}`),
	pipelineError: (err: string) =>
		log('error', 'pipeline', `Failed: ${err}`),

	// Google Drive
	driveConnect: () => log('info', 'drive', 'Starting OAuth flow'),
	driveConnected: (email: string) =>
		log('info', 'drive', `Connected as ${email}`),
	driveUploadStart: (file: string) =>
		log('info', 'drive', `Uploading: ${file}`),
	driveUploadDone: (url: string) =>
		log('info', 'drive', `Uploaded: ${url}`),
	driveError: (err: string) =>
		log('error', 'drive', `Error: ${err}`),

	// General
	info: (category: string, message: string, data?: unknown) =>
		log('info', category, message, data),
	warn: (category: string, message: string, data?: unknown) =>
		log('warn', category, message, data),
	error: (category: string, message: string, data?: unknown) =>
		log('error', category, message, data),
	debug: (category: string, message: string, data?: unknown) =>
		log('debug', category, message, data)
};

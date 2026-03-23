import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('logger', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	async function freshLogger() {
		vi.resetModules();
		const mod = await import('./logger');
		return mod.logger;
	}

	it('configLoaded logs info with [VO:config] prefix and source string', async () => {
		const spy = vi.spyOn(console, 'info').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.configLoaded('localStorage');
		expect(spy).toHaveBeenCalledOnce();
		const args = spy.mock.calls[0];
		expect(args[0]).toBe('%c[VO:config]');
		expect(args[2]).toContain('localStorage');
	});

	it('recordingStart logs capture mode', async () => {
		const spy = vi.spyOn(console, 'info').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.recordingStart('fullscreen');
		expect(spy).toHaveBeenCalledOnce();
		const args = spy.mock.calls[0];
		expect(args[0]).toBe('%c[VO:record]');
		expect(args[2]).toContain('fullscreen');
	});

	it('recordingChunk logs at debug level with chunk index and KB size', async () => {
		const spy = vi.spyOn(console, 'debug').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.recordingChunk(3, 51200);
		expect(spy).toHaveBeenCalledOnce();
		const args = spy.mock.calls[0];
		expect(args[0]).toBe('%c[VO:record]');
		expect(args[2]).toContain('3');
		expect(args[2]).toContain('50.0KB');
	});

	it('pipelineError logs at error level with red color #ef4444', async () => {
		const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.pipelineError('encode failed');
		expect(spy).toHaveBeenCalledOnce();
		const args = spy.mock.calls[0];
		expect(args[0]).toBe('%c[VO:pipeline]');
		expect(args[1]).toBe('color: #ef4444');
		expect(args[2]).toContain('encode failed');
	});

	it('elevenLabsTestResult(false) logs warn with "invalid"', async () => {
		const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.elevenLabsTestResult(false);
		expect(spy).toHaveBeenCalledOnce();
		const args = spy.mock.calls[0];
		expect(args[0]).toBe('%c[VO:elevenlabs]');
		expect(args[2]).toContain('invalid');
	});

	it('elevenLabsTestResult(true) logs info with "valid"', async () => {
		const spy = vi.spyOn(console, 'info').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.elevenLabsTestResult(true);
		expect(spy).toHaveBeenCalledOnce();
		const args = spy.mock.calls[0];
		expect(args[0]).toBe('%c[VO:elevenlabs]');
		expect(args[2]).toContain('valid');
	});

	it('generic info() accepts category and message', async () => {
		const spy = vi.spyOn(console, 'info').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.info('custom', 'hello world');
		expect(spy).toHaveBeenCalledOnce();
		const args = spy.mock.calls[0];
		expect(args[0]).toBe('%c[VO:custom]');
		expect(args[2]).toContain('hello world');
	});

	it('all log messages include HH:MM:SS.mmm timestamp format', async () => {
		const spy = vi.spyOn(console, 'info').mockImplementation(() => {});
		const logger = await freshLogger();
		logger.configLoaded('test');
		const args = spy.mock.calls[0];
		// The timestamp is the first part of the message string (args[2])
		// Format: HH:MM:SS.mmm followed by the message
		expect(args[2]).toMatch(/^\d{2}:\d{2}:\d{2}\.\d{3}\s/);
	});
});

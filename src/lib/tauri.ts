import { invoke } from '@tauri-apps/api/core';

export async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
	return invoke<T>(cmd, args);
}

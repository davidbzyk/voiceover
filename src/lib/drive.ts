import { appState } from '$lib/state.svelte';
import { logger } from '$lib/logger';

/**
 * Typed error for Drive upload failures — preserves HTTP status for retry logic.
 */
export class DriveUploadError extends Error {
	status: number;
	constructor(status: number, body: string) {
		super(`Drive upload failed (${status}): ${body}`);
		this.status = status;
	}
}

/**
 * Refresh the Google Drive OAuth2 access token using the stored refresh token.
 * Updates appState.config with the new token and persists via saveConfig().
 */
export async function refreshDriveToken(): Promise<string> {
	const { client_id, client_secret, refresh_token } = appState.config.google_drive;
	if (!refresh_token) throw new Error('No refresh token — reconnect Google Drive in Settings');

	logger.info('drive', 'Refreshing access token...');
	const resp = await fetch('https://oauth2.googleapis.com/token', {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({
			client_id,
			client_secret,
			refresh_token,
			grant_type: 'refresh_token'
		})
	});

	if (!resp.ok) {
		const body = await resp.text();
		throw new Error(`Token refresh failed: ${body}`);
	}

	const data = await resp.json();
	const newToken = data.access_token;
	const expiresIn = data.expires_in || 3600;
	appState.config.google_drive.access_token = newToken;
	appState.config.google_drive.expires_at = Math.floor(Date.now() / 1000) + expiresIn - 60;
	await appState.saveConfig();
	logger.info('drive', 'Access token refreshed');
	return newToken;
}

/**
 * Upload a blob to Google Drive using the given access token.
 * Returns the webViewLink of the uploaded file.
 * Throws DriveUploadError on non-OK responses (check .status for retry logic).
 */
export async function driveUploadWithToken(blob: Blob, accessToken: string): Promise<string> {
	const metadata = JSON.stringify({
		name: `voiceover-${Date.now()}.webm`,
		mimeType: 'video/webm'
	});

	const form = new FormData();
	form.append('metadata', new Blob([metadata], { type: 'application/json' }));
	form.append('file', blob);

	const resp = await fetch(
		'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink',
		{
			method: 'POST',
			headers: { Authorization: `Bearer ${accessToken}` },
			body: form
		}
	);

	if (!resp.ok) {
		const status = resp.status;
		const body = await resp.text();
		throw new DriveUploadError(status, body);
	}

	const data = await resp.json();

	// Private by default — screen recordings may contain sensitive content.
	// Users can share files manually through Google Drive if needed.

	return data.webViewLink || '';
}

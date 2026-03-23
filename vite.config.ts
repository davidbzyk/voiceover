import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { rmSync } from 'node:fs';
import { resolve } from 'node:path';

/** Strip _config.json from production builds so API keys don't get bundled. */
function stripConfigPlugin() {
	return {
		name: 'strip-config',
		enforce: 'post' as const,
		closeBundle() {
			try {
				rmSync(resolve('build', '_config.json'), { force: true });
			} catch {}
		}
	};
}

export default defineConfig({
	plugins: [sveltekit(), stripConfigPlugin()],
	server: {
		port: 5170,
		strictPort: true
	},
	optimizeDeps: {
		exclude: ['@ffmpeg/ffmpeg', '@ffmpeg/util']
	}
});

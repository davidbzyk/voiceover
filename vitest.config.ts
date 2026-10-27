import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
	plugins: [svelte()],
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}', 'src/**/*.svelte.{test,spec}.{js,ts}'],
		environment: 'jsdom',
		setupFiles: ['./vitest-setup.ts'],
		coverage: {
			provider: 'v8',
			reporter: ['text', 'html', 'text-summary'],
			reportsDirectory: './coverage',
			include: ['src/lib/**/*.{ts,svelte.ts}'],
			exclude: ['src/lib/assets/**', 'src/lib/index.ts'],
			thresholds: {
				statements: 50,
				branches: 50,
				functions: 55,
				lines: 50
			}
		}
	},
	resolve: {
		conditions: ['browser'],
		// Components import through SvelteKit's $lib alias, which only the kit plugin sets up.
		alias: { $lib: new URL('./src/lib', import.meta.url).pathname }
	}
});

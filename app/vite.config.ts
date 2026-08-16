import { sveltekit } from '@sveltejs/kit/vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		svelte({
			include: ['src/lib/**/*.ts', 'tests/**/*.ts'],
experimental: {
				compileModule: {
					include: ['src/lib/**/*.ts', 'tests/**/*.ts'],
					infixes: ['']
				}
			}
		})
	],
	server: {
		port: 5173,
		strictPort: true
	},
	clearScreen: false,
	envPrefix: ['VITE_', 'TAURI_ENV_']
});

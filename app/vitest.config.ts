import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
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
	resolve: {
		alias: {
			$lib: new URL('./src/lib', import.meta.url).pathname
		}
	},
	test: {
		environment: 'jsdom',
		include: ['tests/unit/**/*.test.ts']
	}
});

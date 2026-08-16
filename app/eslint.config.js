import eslintPluginSvelte from 'eslint-plugin-svelte';
import tseslint from 'typescript-eslint';

export default tseslint.config(
	...tseslint.configs.recommended,
	...eslintPluginSvelte.configs['flat/recommended'],
	{
		ignores: [
			'build/**',
			'.svelte-kit/**',
			'src-tauri/**',
			'node_modules/**',
			'static/**'
		]
	},
	{
		files: ['**/*.svelte'],
		languageOptions: {
			parserOptions: {
				parser: tseslint.parser
			}
		}
	},
	{
		rules: {
			'@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
			'@typescript-eslint/no-explicit-any': 'warn'
		}
	}
);
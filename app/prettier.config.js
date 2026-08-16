/** @type {import("prettier").Config} */
export default {
	useTabs: true,
	tabWidth: 2,
	singleQuote: true,
	printWidth: 100,
	trailingComma: 'none',
	plugins: ['prettier-plugin-svelte'],
	overrides: [{ files: '*.svelte', options: { parser: 'svelte' } }]
};
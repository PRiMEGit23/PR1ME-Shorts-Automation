<script lang="ts">
	/**
	 * Root layout — single SPA route (PRODUCT_LAYER §3): boot then shell.
	 */
	import { bootstrap, store } from '../main';
	import { di } from '$lib/core/di';
	import WindowShell from '$lib/components/shell/WindowShell.svelte';

	let { children }: { children?: import('svelte').Snippet } = $props();

	$effect(() => {
		void bootstrap(di);
	});
</script>

<WindowShell
	ui={store.ui}
	layout={store.layout}
	editor={store.editor}
	app={store}
	providers={store.providers}
	connections={store.connections}
	knowledge={store.knowledge}
	script={store.script}
>
	{@render children?.()}
</WindowShell>
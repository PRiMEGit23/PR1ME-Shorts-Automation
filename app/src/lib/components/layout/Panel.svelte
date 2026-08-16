<script lang="ts">
	/**
	 * Panel — dock panel: 40px header + body (VDS §30/§35: panel).
	 */
	import PanelHeader from './PanelHeader.svelte';
	import type { LayoutStore } from '$lib/stores/layout.store';
	import type { UiStore } from '$lib/stores/ui.store';

	let {
		id,
		title,
		layout,
		ui,
		children
	}: {
		id: string;
		title: string;
		layout: LayoutStore;
		ui: UiStore;
		children?: import('svelte').Snippet;
	} = $props();
</script>

<section class="panel">
	<PanelHeader {title} panelId={id} {layout} {ui} />
	<div class="body">{@render children?.()}</div>
</section>

<style>
	.panel {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		flex: 1;
		background: var(--surface-1);
		border: 1px solid var(--border-default);
		border-radius: var(--radius-md);
		overflow: hidden;
	}
	.body {
		flex: 1;
		min-height: 0;
		overflow: auto;
	}
</style>
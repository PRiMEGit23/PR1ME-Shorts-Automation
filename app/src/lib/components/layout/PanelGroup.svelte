<script lang="ts">
	/**
	 * PanelGroup — layout container: vertical stack (left/right zones) or
	 * horizontal row (bottom zone). 4px gaps on the grid (VDS §9).
	 */
	let {
		direction = 'vertical',
		children
	}: { direction?: 'vertical' | 'horizontal'; children?: import('svelte').Snippet } = $props();
</script>

<div class="group" class:horizontal={direction === 'horizontal'}>
	{@render children?.()}
</div>

<style>
	.group {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		flex: 1;
		min-width: 0;
		min-height: 0;
		padding: var(--space-1);
	}
	.group.horizontal {
		flex-direction: row;
	}
</style>
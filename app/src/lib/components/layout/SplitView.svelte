<script lang="ts">
	/**
	 * SplitView — nested split container. 2S1: single root child; splits
	 * (2P4) arrive with the editor in later phases. 4px dividers.
	 */
	import DragHandle from './DragHandle.svelte';

	let {
		direction = 'horizontal',
		children
	}: { direction?: 'horizontal' | 'vertical'; children?: import('svelte').Snippet } = $props();
</script>

<div class="split" class:vertical={direction === 'vertical'}>
	{#if children}
		<div class="pane">
			{@render children?.()}
		</div>
	{/if}
</div>

<style>
	.split {
		display: flex;
		min-width: 0;
		min-height: 0;
		flex: 1;
	}
	.split.vertical {
		flex-direction: column;
	}
	.pane {
		flex: 1;
		min-width: 0;
		min-height: 0;
		display: flex;
	}
</style>
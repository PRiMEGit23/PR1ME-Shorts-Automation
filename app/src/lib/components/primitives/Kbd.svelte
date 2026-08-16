<script lang="ts">
	/**
	 * Kbd — keyboard chip (VDS §35: kbd).
	 */
	let { children }: { children?: import('svelte').Snippet } = $props();
</script>

<kbd class="kbd">{@render children?.()}</kbd>

<style>
	.kbd {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 18px;
		min-width: 20px;
		padding: 0 var(--space-2);
		border-radius: var(--kbd-radius);
		border: 1px solid var(--kbd-border);
		background: var(--kbd-bg);
		font: var(--mono-xs);
		color: var(--text-secondary);
		white-space: nowrap;
	}
</style>
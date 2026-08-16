<script lang="ts">
	/**
	 * Tooltip — glass tooltip on hover (VDS §35: tooltip, 120ms delay).
	 * Edge tooltips flip to bottom via `below` prop.
	 */
	let { label, below = false, children }: { label: string; below?: boolean; children?: import('svelte').Snippet } = $props();
</script>

<span class="wrap" class:below>
	{@render children?.()}
	<span class="tip" role="tooltip">{label}</span>
</span>

<style>
	.wrap {
		position: relative;
		display: inline-flex;
	}
	.tip {
		position: absolute;
		left: 50%;
		bottom: calc(100% + 6px);
		transform: translateX(-50%) translateY(2px);
		z-index: var(--z-tooltip);
		padding: var(--space-1) var(--space-2);
		border-radius: var(--radius-sm);
		border: 1px solid var(--border-default);
		background: var(--glass-bg);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		font: var(--body-xs);
		color: var(--text-primary);
		white-space: nowrap;
		opacity: 0;
		pointer-events: none;
		transition:
			opacity var(--motion-fast) var(--ease-out) 120ms,
			transform var(--motion-fast) var(--ease-out) 120ms;
	}
	.wrap:hover .tip {
		opacity: 1;
		transform: translateX(-50%) translateY(0);
	}
	.wrap.below .tip {
		bottom: auto;
		top: calc(100% + 6px);
		transform: translateX(-50%) translateY(-2px);
	}
	.wrap.below:hover .tip {
		transform: translateX(-50%) translateY(0);
	}
</style>
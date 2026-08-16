<script lang="ts">
	/**
	 * ChainNode — one row of the 15-stage prompt chain rail (UX §12):
	 * status icon, stage name, duration ms, cache-hit badge (⇄). Clicking
	 * selects the stage — its contract renders in the Inspector.
	 */
	import type { PromptStage } from '$lib/models/storyboard';

	let {
		stage,
		index,
		selected,
		onselect
	}: {
		stage: PromptStage;
		index: number;
		selected: boolean;
		onselect: () => void;
	} = $props();
</script>

<button
	class="node {stage.status}"
	class:selected
	role="option"
	aria-selected={selected}
	onclick={onselect}
>
	<span class="idx mono">{index + 1}</span>
	<span class="dot" aria-hidden="true"></span>
	<span class="name">{stage.name}</span>
	{#if stage.cache_hit}
		<span class="cache" title="cache hit">⇄</span>
	{/if}
	{#if stage.has_artifact}
		<span class="art mono" title="stage artifact available">out</span>
	{/if}
	<span class="dur mono">{stage.duration_ms != null ? `${stage.duration_ms} ms` : ''}</span>
</button>

<style>
	.node {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		height: 32px;
		padding: 0 10px;
		border: 1px solid transparent;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-primary);
		cursor: pointer;
		text-align: left;
	}
	.node:hover {
		background: var(--surface-2);
	}
	.node.selected {
		border-color: var(--accent);
		background: var(--accent-soft);
	}
	.idx {
		font-size: 9px;
		color: var(--text-tertiary);
		width: 14px;
		flex-shrink: 0;
	}
	.dot {
		width: 8px;
		height: 8px;
		flex-shrink: 0;
		border-radius: 50%;
		border: 1px solid var(--border-strong);
	}
	.node.completed .dot {
		background: var(--status-ok);
		border-color: var(--status-ok);
	}
	.node.running .dot {
		background: var(--accent);
		border-color: var(--accent);
		animation: pulse 1.2s ease-in-out infinite;
	}
	.node.failed .dot {
		background: var(--status-error);
		border-color: var(--status-error);
	}
	.node.skipped {
		opacity: 0.55;
	}
	.node.pending .dot {
		border-color: var(--border-strong);
	}
	.name {
		font-size: 12px;
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.node.completed .name {
		color: var(--text-primary);
	}
	.node.running .name {
		color: var(--accent);
	}
	.cache {
		font-size: 11px;
		color: var(--text-tertiary);
		flex-shrink: 0;
	}
	.art {
		font-size: 9px;
		color: var(--accent);
		flex-shrink: 0;
	}
	.dur {
		font-size: 10px;
		color: var(--text-tertiary);
		font-variant-numeric: tabular-nums;
		flex-shrink: 0;
	}
	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.3;
		}
	}
</style>

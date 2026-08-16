<script lang="ts">
	/**
	 * PipelineStrip — the 10-stage visual pipeline (IMPLEMENTATION_PLAN 2S4
	 * Workflow): Knowledge Base → … → Winner. Statuses derive from the
	 * 15-stage chain plus render history (QA / Optimizer / Winner).
	 */
	import type { PipelineStageView } from '$lib/stores/workflow.store';

	let { stages }: { stages: PipelineStageView[] } = $props();
</script>

<div class="pipeline" role="list" aria-label="Visual pipeline">
	{#each stages as stage, i (stage.id)}
		{#if i > 0}
			<span class="conn" aria-hidden="true"></span>
		{/if}
		<div class="node {stage.status}" title={`${stage.label} · ${stage.status}`}>
			<span class="dot" aria-hidden="true"></span>
			<span class="name">{stage.label}</span>
			<span class="sub mono">{stage.sub}</span>
		</div>
	{/each}
</div>

<style>
	.pipeline {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px var(--space-4);
		overflow-x: auto;
		scrollbar-width: none;
		background: var(--surface-1);
		border-bottom: 1px solid var(--border-subtle);
	}
	.conn {
		width: 18px;
		height: 1.5px;
		background: var(--border-default);
		flex-shrink: 0;
	}
	.node {
		display: flex;
		flex-direction: column;
		gap: 1px;
		padding: 6px 10px;
		border: 1px solid var(--border-default);
		border-radius: var(--radius-sm);
		background: var(--surface-0);
		flex-shrink: 0;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		border: 1px solid var(--border-strong);
		margin-bottom: 2px;
	}
	.node.ok {
		border-color: var(--status-ok);
	}
	.node.ok .dot {
		background: var(--status-ok);
		border-color: var(--status-ok);
	}
	.node.running {
		border-color: var(--accent);
	}
	.node.running .dot {
		background: var(--accent);
		border-color: var(--accent);
		animation: pulse 1.2s ease-in-out infinite;
	}
	.node.failed {
		border-color: var(--status-error);
	}
	.node.failed .dot {
		background: var(--status-error);
		border-color: var(--status-error);
	}
	.node.skipped {
		opacity: 0.5;
	}
	.node.skipped .dot {
		background: var(--text-tertiary);
		border-color: var(--text-tertiary);
	}
	.name {
		font-size: 11px;
		font-weight: 600;
		color: var(--text-primary);
		white-space: nowrap;
	}
	.sub {
		font-size: 9px;
		color: var(--text-tertiary);
		white-space: nowrap;
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

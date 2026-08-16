<script lang="ts">
	/**
	 * StageRail — live 15-node pipeline rail (VDS §14: top strip 36 px,
	 * icon + index, 1 px connectors; states per §18).
	 */
	import { STAGE_ORDER } from '$lib/models/storyboard';
	import type { PromptStage } from '$lib/models/storyboard';

	let {
		stages,
		compact = false
	}: {
		stages: PromptStage[];
		compact?: boolean;
	} = $props();

	const byId = $derived(new Map(stages.map((s) => [s.stage_id, s])));
	const STATE_GLYPH: Record<string, string> = {
		completed: 'check',
		running: 'dot',
		failed: 'close',
		skipped: 'minus'
	};
</script>

<div class="rail" class:compact role="list" aria-label="Pipeline stages">
	{#each STAGE_ORDER as stageId, i (stageId)}
		{@const stage = byId.get(stageId)}
		{@const status = stage?.status ?? 'pending'}
		{@const glyph = STATE_GLYPH[status] ?? 'dot'}
		{#if i > 0}
			<span class="connector" aria-hidden="true"></span>
		{/if}
		<div
			class="node {status}"
			title={`${stageId} · ${status}${stage?.duration_ms != null ? ` · ${stage.duration_ms} ms` : ''}`}
		>
			<span class="idx mono">{i + 1}</span>
			<span class="g-icon" aria-hidden="true"></span>
			{#if !compact}
				<span class="name" title={stageId}>{stage?.name ?? stageId}</span>
			{/if}
			{#if stage?.cache_hit}
				<span class="cache" title="cache hit">⇄</span>
			{/if}
		</div>
	{/each}
</div>

<style>
	.rail {
		display: flex;
		align-items: center;
		height: 36px;
		padding: 0 var(--space-4);
		overflow-x: auto;
		scrollbar-width: none;
		background: var(--surface-1);
		border-bottom: 1px solid var(--border-subtle);
	}
	.connector {
		width: 8px;
		height: 1px;
		background: var(--border-subtle);
		flex-shrink: 0;
	}
	.node {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 0 6px;
		height: 28px;
		border-radius: 4px;
		flex-shrink: 0;
		cursor: default;
	}
	.node:hover {
		background: var(--surface-2);
	}
	.idx {
		font-size: 9px;
		color: var(--text-tertiary);
	}
	.node.completed .g-icon {
		width: 8px;
		height: 8px;
		border-radius: 2px;
		background: var(--status-ok);
	}
	.node.running .g-icon {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--accent);
		animation: pulse 1.2s ease-in-out infinite;
	}
	.node.failed .g-icon {
		width: 8px;
		height: 8px;
		background: var(--status-error);
		transform: rotate(45deg);
	}
	.node.skipped .g-icon {
		width: 8px;
		height: 2px;
		background: var(--text-tertiary);
	}
	.node.pending .g-icon {
		width: 6px;
		height: 6px;
		border: 1px solid var(--border-strong);
		border-radius: 50%;
	}
	.name {
		font-size: 10.5px;
		color: var(--text-secondary);
		white-space: nowrap;
		max-width: 130px;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.node.completed .name {
		color: var(--text-primary);
	}
	.node.running .name {
		color: var(--accent);
	}
	.cache {
		font-size: 10px;
		color: var(--text-tertiary);
	}
	.rail.compact .name {
		display: none;
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

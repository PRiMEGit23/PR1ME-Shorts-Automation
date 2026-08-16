<script lang="ts">
	/**
	 * WorkflowInspector — right-dock inspector for the Workflow workbench:
	 * selection-driven (UX §12): stage contract in a JsonView, selected
	 * graph node values + rationale placeholder, or the per-scene prompt
	 * chain (PromptChainInspector).
	 */
	import JsonView from '$lib/components/data/JsonView.svelte';
	import PromptChainInspector from '$lib/components/domain/PromptChainInspector.svelte';
	import type { WorkflowStore } from '$lib/stores/workflow.store';
	import type { StoryboardStore } from '$lib/stores/storyboard.store';

	let {
		store,
		storyboard
	}: {
		store: WorkflowStore;
		storyboard: StoryboardStore;
	} = $props();

	const selectedScene = $derived(
		storyboard.sceneViews.find((v) => v.scene.scene_id === store.selectedSceneId) ?? null
	);
	const selectedNodes = $derived(
		[...store.selectedNodeIds]
			.map((id) => store.graph.nodes.find((n) => n.id === id))
			.filter((n): n is NonNullable<typeof n> => !!n)
	);
</script>

<div class="inspector">
	{#if store.activeStage}
		<section class="block">
			<h4 class="label">STAGE</h4>
			<dl class="meta mono">
				<div><dt>status</dt><dd>{store.activeStage.status}</dd></div>
				<div><dt>duration</dt>
					<dd>{store.activeStage.duration_ms != null ? `${store.activeStage.duration_ms} ms` : '—'}</dd>
				</div>
				<div><dt>cache</dt><dd>{store.activeStage.cache_hit ? 'hit' : 'miss'}</dd></div>
			</dl>
		</section>
		<section class="block">
			<h4 class="label">CONTRACT</h4>
			{#if store.activeStage.artifact !== null}
				<JsonView
					readonly
					column={store.activeStage.stage_id}
					value={JSON.stringify(store.activeStage.artifact, null, 2)}
					onchange={() => undefined}
				/>
			{:else}
				<p class="muted mono">no artifact yet for {store.activeStage.stage_id}</p>
			{/if}
		</section>
	{:else if selectedNodes.length > 0}
		<section class="block">
			<h4 class="label">NODE{selectedNodes.length > 1 ? 'S' : ''}</h4>
			{#each selectedNodes as node (node.id)}
				<div class="node-box">
					<h5 class="label">{node.label}</h5>
					<dl class="meta mono">
						{#each node.values as [key, value] (key + value)}
							<div><dt>{key}</dt><dd title={value}>{value}</dd></div>
						{/each}
					</dl>
				</div>
			{/each}
		</section>
		<section class="block rationale">
			<h4 class="label">RATIONALE</h4>
			<p class="muted mono">
				Compile-log rationale is not part of this artifact — it arrives with the
				WorkflowCompileLog (placeholder).
			</p>
		</section>
	{:else if selectedScene}
		<section class="block">
			<h4 class="label">PROMPT CHAIN · {selectedScene.scene.scene_id}</h4>
			<PromptChainInspector view={selectedScene} />
		</section>
	{:else}
		<p class="muted mono">select a stage, a node, or a scene to inspect it here.</p>
	{/if}
</div>

<style>
	.inspector {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
		padding: var(--space-4);
		overflow-y: auto;
	}
	.block {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.block h4,
	.block h5 {
		margin: 0;
	}
	.meta {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
	}
	.meta div {
		display: flex;
		justify-content: space-between;
		gap: 10px;
	}
	.meta dt {
		color: var(--text-tertiary);
		font-size: 10.5px;
		white-space: nowrap;
	}
	.meta dd {
		margin: 0;
		color: var(--text-primary);
		font-size: 10.5px;
		text-align: right;
		max-width: 160px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.node-box {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px;
		border: 1px solid var(--border-default);
		border-radius: var(--radius-sm);
		background: var(--surface-1);
	}
	.rationale {
		padding: 10px;
		border-radius: var(--radius-sm);
		background: var(--status-info-soft);
		border: 1px solid var(--status-info);
	}
	.muted {
		margin: 0;
		font-size: 10.5px;
		color: var(--text-tertiary);
		line-height: 1.5;
	}
</style>

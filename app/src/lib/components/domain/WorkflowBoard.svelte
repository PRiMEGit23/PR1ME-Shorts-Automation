<script lang="ts">
	/**
	 * WorkflowBoard — the Workflow workbench (IMPLEMENTATION_PLAN 2S4):
	 * per-scene selector (S1..S5 + THUMB), the 10-stage visual pipeline
	 * strip, the 15-stage prompt chain (view `1`), the per-scene ComfyUI
	 * workflow graph (view `2`, zoom/pan/fit/minimap), export + copy of the
	 * scene's workflow JSON.
	 */
	import { onMount } from 'svelte';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import GraphCanvas from '$lib/components/domain/GraphCanvas.svelte';
	import PipelineStrip from '$lib/components/domain/PipelineStrip.svelte';
	import PromptChain from '$lib/components/domain/PromptChain.svelte';
	import type { WorkflowStore } from '$lib/stores/workflow.store';
	import type { WorkflowVm } from '$lib/viewmodels/workflow.vm';

	let {
		store,
		vm
	}: {
		store: WorkflowStore;
		vm: WorkflowVm;
	} = $props();

	function onKeydown(e: KeyboardEvent) {
		if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
		if (e.key === '1') {
			store.viewMode = 'chain';
		} else if (e.key === '2') {
			store.viewMode = 'graph';
		} else if (e.key === 'w' || e.key === 'W') {
			vm.fit();
		} else if (e.key === 'Delete' || e.key === 'Backspace') {
			vm.clearSelection();
		}
	}

	onMount(() => {
		vm.open();
	});
</script>

<svelte:window onkeydown={onKeydown} />

<div class="board" role="region" aria-label="Workflow workbench">
	<header class="bar">
		<h3 class="title">Workflow</h3>
		{#if store.storyboardViews.length > 0}
			<div class="scenes" role="tablist" aria-label="Select scene">
				{#each store.storyboardViews as view (view.scene.scene_id)}
					<button
						class="chip"
						class:active={store.selectedSceneId === view.scene.scene_id}
						role="tab"
						aria-selected={store.selectedSceneId === view.scene.scene_id}
						onclick={() => vm.selectScene(view.scene.scene_id)}
					>
						{view.scene.scene_id}
					</button>
				{/each}
			</div>
		{/if}
		<span class="spacer"></span>
		{#if store.viewMode === 'graph'}
			<span class="group">
				<IconButton icon="zoom-out" label="Zoom out" size={24} iconSize={13} onclick={vm.zoomOut} />
				<span class="zoom mono">{Math.round(store.zoom * 100)}%</span>
				<IconButton icon="zoom-in" label="Zoom in" size={24} iconSize={13} onclick={vm.zoomIn} />
				<IconButton icon="fit" label="Fit graph (W)" size={24} iconSize={13} onclick={vm.fit} />
			</span>
		{/if}
		<span class="group view-toggle" role="group" aria-label="View">
			<button class="toggle" class:active={store.viewMode === 'chain'} onclick={() => (store.viewMode = 'chain')}>
				1
			</button>
			<button class="toggle" class:active={store.viewMode === 'graph'} onclick={() => (store.viewMode = 'graph')}>
				2
			</button>
		</span>
		<IconButton icon="copy" label="Copy workflow JSON" size={24} iconSize={13}
			disabled={!store.workflow}
			onclick={vm.copyJson}
		/>
		<IconButton icon="code" label="Export workflow JSON" size={24} iconSize={13}
			disabled={!store.workflow}
			onclick={vm.exportJson}
		/>
	</header>

	<PipelineStrip stages={store.pipeline} />

	{#if store.viewMode === 'chain'}
		<div class="chain-wrap">
			{#if store.chainLoading}
				<p class="meta mono">loading prompt chain…</p>
			{:else if store.chainError}
				<p class="meta mono error">{store.chainError}</p>
			{/if}
			<PromptChain
				stages={store.chain}
				activeStageId={store.activeStageId}
				{vm}
			/>
		</div>
	{:else}
		<GraphCanvas {store} {vm} />
	{/if}
</div>

<style>
	.board {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		background: var(--surface-0);
	}
	.bar {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		padding: var(--space-3) var(--space-4);
		background: var(--surface-1);
		border-bottom: 1px solid var(--border-subtle);
	}
	.title {
		margin: 0;
		font: var(--h3);
		color: var(--text-primary);
	}
	.scenes {
		display: flex;
		gap: 4px;
	}
	.chip {
		height: 24px;
		padding: 0 10px;
		border: 1px solid var(--border-default);
		border-radius: 999px;
		background: var(--surface-0);
		color: var(--text-secondary);
		font: var(--label);
		cursor: pointer;
	}
	.chip:hover {
		border-color: var(--border-strong);
	}
	.chip.active {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}
	.spacer {
		flex: 1;
	}
	.group {
		display: flex;
		align-items: center;
		gap: 2px;
	}
	.zoom {
		font-size: 10.5px;
		color: var(--text-tertiary);
		min-width: 42px;
		text-align: center;
	}
	.view-toggle {
		border: 1px solid var(--border-default);
		border-radius: var(--radius-sm);
		overflow: hidden;
	}
	.toggle {
		width: 26px;
		height: 24px;
		border: none;
		background: transparent;
		color: var(--text-tertiary);
		font: var(--label);
		cursor: pointer;
	}
	.toggle.active {
		background: var(--accent);
		color: var(--surface-0);
	}
	.chain-wrap {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		padding: var(--space-3);
		overflow-y: auto;
	}
	.meta {
		margin: 0;
		font-size: 10.5px;
		color: var(--text-tertiary);
	}
	.meta.error {
		color: var(--status-error);
	}
</style>

<script lang="ts">
	/**
	 * StoryboardBoard — Storyboard workbench (UX §11 / VDS §14): stage rail,
	 * scene board canvas (blueprint grid, zoom 50–200 %, pan, fit) with a
	 * filmstrip of SceneCards, timeline strip, and keyboard navigation
	 * (N/P, ←/→, +/− zoom, F fit, Space reset).
	 */
	import { onMount } from 'svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import Button from '$lib/components/primitives/Button.svelte';
	import StageRail from '$lib/components/domain/StageRail.svelte';
	import SceneCard from '$lib/components/domain/SceneCard.svelte';
	import Timeline from '$lib/components/domain/Timeline.svelte';
	import EmptyState from '$lib/components/layout/EmptyState.svelte';
	import { chainFromBundle } from '$lib/stores/workflow.store';
	import type { PromptStage } from '$lib/models/storyboard';
	import type { UiStore } from '$lib/stores/ui.store';
	import type { StoryboardStore } from '$lib/stores/storyboard.store';
	import type { StoryboardVm } from '$lib/viewmodels/storyboard.vm';

	let {
		ui,
		store,
		vm
	}: {
		ui: UiStore;
		store: StoryboardStore;
		vm: StoryboardVm;
	} = $props();

	let dragging = $state(false);
	let lastX = 0;
	let lastY = 0;
	let dragStart: { x: number; y: number } | null = null;
	let moved = false;

	onMount(() => {
		void vm.open();
	});

	const reportStages = $derived.by(() => {
		if (!store.bundle?.report?.stages) return [] as PromptStage[];
		return store.bundle.report.stages.map((s) => ({
			stage_id: s.stage_id,
			name: s.name ?? s.stage_id,
			status: s.status,
			duration_ms: s.duration_ms ?? null,
			cache_hit: s.cache_hit ?? null,
			has_artifact: false,
			artifact: null
		}));
	});
	const railStages = $derived(chainFromBundle(reportStages));

	function onCanvasKeydown(e: KeyboardEvent) {
		if (ui.workbench !== 'storyboard') return;
		const target = e.target as HTMLElement | null;
		if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;
		switch (e.key) {
			case 'n':
			case 'N':
			case 'ArrowRight':
				e.preventDefault();
				vm.stepScene(1);
				break;
			case 'p':
			case 'P':
			case 'ArrowLeft':
				e.preventDefault();
				vm.stepScene(-1);
				break;
			case '+':
			case '=':
				e.preventDefault();
				vm.zoomIn();
				break;
			case '-':
				e.preventDefault();
				vm.zoomOut();
				break;
			case 'f':
			case 'F':
				e.preventDefault();
				vm.fit();
				break;
			case ' ':
				e.preventDefault();
				store.pan(0, 0);
				break;
		}
	}

	function onPointerDown(e: PointerEvent) {
		if (e.button !== 0) return;
		dragging = true;
		moved = false;
		lastX = e.clientX;
		lastY = e.clientY;
		dragStart = { x: e.clientX, y: e.clientY };
	}

	function onPointerMove(e: PointerEvent) {
		if (!dragging) return;
		const dx = e.clientX - lastX;
		const dy = e.clientY - lastY;
		lastX = e.clientX;
		lastY = e.clientY;
		if (Math.abs(e.clientX - (dragStart?.x ?? e.clientX)) > 3 || moved) {
			moved = true;
			vm.pan(dx, dy);
		}
	}

	function onPointerUp() {
		dragging = false;
	}

	function onWheel(e: WheelEvent) {
		if (!e.ctrlKey && !e.metaKey) return;
		e.preventDefault();
		const delta = e.deltaY > 0 ? -0.1 : 0.1;
		vm.zoom(delta);
	}
</script>

<svelte:window onkeydown={onCanvasKeydown} />

{#if store.bundle}
	<div class="board">
		<header class="head">
			<div class="h-left">
				<span class="label">STORYBOARD</span>
				<span class="topic mono">{store.bundle.topic || 'untitled run'}</span>
				<span class="run mono">run {store.bundle.run_id}</span>
				{#if !store.knowledgeRow}
					<span class="warn mono" title="No knowledge base row matched this topic — plan chips show —.">
						plan not found in KB
					</span>
				{/if}
			</div>
			<div class="h-right">
				<span class="zoom mono">{Math.round(store.zoom * 100)}%</span>
				<IconButton icon="zoom-out" label="Zoom out (−)" onclick={() => vm.zoomOut()} />
				<IconButton icon="zoom-in" label="Zoom in (+)" onclick={() => vm.zoomIn()} />
				<IconButton icon="fit" label="Fit board (F)" onclick={() => vm.fit()} />
				<Button variant="secondary" icon="refresh" title="Reload the latest run" onclick={() => void vm.open()}>
					Reload
				</Button>
			</div>
		</header>
		<StageRail stages={railStages} />
		<div class="canvas" role="application" aria-label="Scene board canvas"
			onpointerdown={onPointerDown} onpointermove={onPointerMove}
			onpointerup={onPointerUp} onpointerleave={onPointerUp} onwheel={onWheel}
		>
			<div class="viewport" style="transform: translate({store.panX}px, {store.panY}px) scale({store.zoom})">
				<div class="filmstrip">
					{#each store.sceneViews as view, i (view.scene.scene_id)}
						<SceneCard
							{view}
							selected={view.scene.scene_id === store.selectedSceneId}
							approvedAttemptId={store.approvedFor(view.scene.scene_id)}
							{vm}
							last={i === store.sceneViews.length - 1}
						/>
					{/each}
				</div>
			</div>
			{#if store.loading}
				<div class="busy mono">loading run…</div>
			{/if}
		</div>
		<Timeline
			clips={store.clips}
			totalRuntime={store.totalRuntime}
			hasDurations={store.hasDurations}
			selectedSceneId={store.selectedSceneId}
			{vm}
		/>
	</div>
{:else}
	<EmptyState
		icon="storyboard"
		title={store.error ? 'Storyboard not loaded' : 'No runs yet'}
		subtitle={store.error ?? 'Generate an episode to board scenes here — the latest run loads automatically.'}
	>
		{#snippet children()}
			<Button variant="secondary" icon="refresh" onclick={() => void vm.open()}>
				{store.loading ? 'Loading…' : 'Reload'}
			</Button>
		{/snippet}
	</EmptyState>
{/if}

<style>
	.board {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
		min-width: 0;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
		padding: var(--space-3) var(--space-4);
		border-bottom: 1px solid var(--border-subtle);
		flex-shrink: 0;
	}
	.h-left,
	.h-right {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		min-width: 0;
	}
	.topic {
		font-size: 12px;
		color: var(--text-primary);
		max-width: 240px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.run {
		font-size: 10px;
		color: var(--text-tertiary);
	}
	.warn {
		font-size: 10px;
		color: var(--status-warning);
	}
	.zoom {
		font-size: 10.5px;
		color: var(--text-tertiary);
		font-variant-numeric: tabular-nums;
	}
	.canvas {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		position: relative;
		background-image: var(--canvas-grid);
		background-size: var(--canvas-grid-size) var(--canvas-grid-size);
		cursor: grab;
		touch-action: none;
	}
	.canvas:active {
		cursor: grabbing;
	}
	.viewport {
		position: absolute;
		top: 0;
		left: 0;
		transform-origin: 0 0;
		will-change: transform;
	}
	.filmstrip {
		display: flex;
		align-items: flex-start;
		gap: 26px;
		padding: 48px;
		width: max-content;
	}
	.busy {
		position: absolute;
		top: 12px;
		right: 16px;
		font-size: 10.5px;
		color: var(--text-tertiary);
		animation: pulse 1.2s ease-in-out infinite;
	}
	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.4;
		}
	}
</style>

<script lang="ts">
	/**
	 * GraphCanvas — ComfyUI workflow canvas (UX §12 / VDS §13): blueprint
	 * grid, infinite pan, zoom 50–200 %, fit, minimap 160×100, node
	 * selection (Cmd/Ctrl+Click multi-select, Del clears), hovered edge
	 * accent. Read-only — honest rendering of the BackendWorkflow fields.
	 */
	import { onMount } from 'svelte';
	import WorkflowNode from '$lib/components/domain/WorkflowNode.svelte';
	import type { WorkflowGraph } from '$lib/models/storyboard';
	import type { WorkflowStore } from '$lib/stores/workflow.store';
	import type { WorkflowVm } from '$lib/viewmodels/workflow.vm';

	const NODE_W = 220;
	const HEADER_H = 32;
	const LAYER_GAP = 280;
	const ROW_GAP = 120;
	const PAD = 48;

	let {
		store,
		vm
	}: {
		store: WorkflowStore;
		vm: WorkflowVm;
	} = $props();

	let container: HTMLDivElement;
	let dragging = $state(false);
	let lastX = 0;
	let lastY = 0;
	let dragStart: { x: number; y: number } | null = null;
	let moved = false;

	/** Deterministic layered layout (no auto-layout engine — stable x/y). */
	const layout = $derived.by(() => {
		const pos = new Map<string, { x: number; y: number }>();
		const perLayer = new Map<number, number>();
		for (const node of store.graph.nodes) {
			const i = perLayer.get(node.layer) ?? 0;
			perLayer.set(node.layer, i + 1);
			pos.set(node.id, {
				x: PAD + node.layer * LAYER_GAP,
				y: PAD + i * ROW_GAP
			});
		}
		let width = PAD * 2;
		let height = PAD * 2;
		for (const [layer, count] of perLayer) {
			width = Math.max(width, PAD + (layer + 1) * LAYER_GAP);
			height = Math.max(height, PAD + count * ROW_GAP);
		}
		return { pos, width, height };
	});

	const outIds = $derived(new Set(store.graph.edges.map((e) => e.from)));
	const inIds = $derived(new Set(store.graph.edges.map((e) => e.to)));

	const miniW = 160;
	const miniH = 100;

	function fit() {
		if (store.graph.nodes.length === 0) {
			vm.fit();
			return;
		}
		const cw = container?.clientWidth ?? 800;
		const ch = container?.clientHeight ?? 500;
		const zoom = Math.max(
			0.5,
			Math.min(2, Math.min((cw - 40) / layout.width, (ch - 40) / layout.height))
		);
		store.setZoom(zoom);
		store.pan((cw - layout.width * zoom) / 2, (ch - layout.height * zoom) / 2);
	}

	onMount(() => {
		fit();
	});

	function onWheel(e: WheelEvent) {
		if (!e.ctrlKey && !e.metaKey) return;
		e.preventDefault();
		if (e.deltaY > 0) {
			vm.zoomOut();
		} else {
			vm.zoomIn();
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
		// empty-canvas click clears the selection (node clicks never start a drag)
		if (dragging && !moved) {
			vm.clearSelection();
		}
		dragging = false;
	}

	function edgePath(fromId: string, toId: string): string {
		const a = layout.pos.get(fromId);
		const b = layout.pos.get(toId);
		if (!a || !b) return '';
		const x1 = a.x + NODE_W;
		const y1 = a.y + HEADER_H;
		const x2 = b.x;
		const y2 = b.y + HEADER_H;
		const mx = (x1 + x2) / 2;
		return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
	}

	/** Minimap scale + viewport rect in minimap space (clamped to bounds). */
	const mini = $derived.by(() => {
		const scale = Math.min(miniW / layout.width, miniH / layout.height);
		const gw = layout.width * scale;
		const gh = layout.height * scale;
		const offX = (miniW - gw) / 2;
		const offY = (miniH - gh) / 2;
		const cw = container?.clientWidth ?? 800;
		const ch = container?.clientHeight ?? 500;
		const vw = Math.min(gw, (cw / Math.max(0.001, store.zoom)) * scale);
		const vh = Math.min(gh, (ch / Math.max(0.001, store.zoom)) * scale);
		const vx = Math.max(0, Math.min(gw - vw, offX + (-store.panX / Math.max(0.001, store.zoom)) * scale));
		const vy = Math.max(0, Math.min(gh - vh, offY + (-store.panY / Math.max(0.001, store.zoom)) * scale));
		return { scale, offX, offY, vw, vh, vx, vy };
	});
</script>

<div class="canvas" role="application" aria-label="Workflow graph canvas"
	bind:this={container} onwheel={onWheel}
	onpointerdown={onPointerDown} onpointermove={onPointerMove}
	onpointerup={onPointerUp} onpointerleave={onPointerUp}
>
	<svg class="edges" width={layout.width} height={layout.height} aria-hidden="true">
		{#each store.graph.edges as edge (edge.from + '>' + edge.to)}
			<path class="edge" d={edgePath(edge.from, edge.to)} />
		{/each}	</svg>
	<div class="world" style="transform: translate({store.panX}px, {store.panY}px) scale({store.zoom})">
		{#each store.graph.nodes as node (node.id)}
			<WorkflowNode
				{node}
				x={layout.pos.get(node.id)?.x ?? 0}
				y={layout.pos.get(node.id)?.y ?? 0}
				selected={store.selectedNodeIds.has(node.id)}
				connectedOut={outIds.has(node.id)}
				connectedIn={inIds.has(node.id)}
				onselect={(additive) => vm.selectNode(node.id, additive)}
			/>
		{/each}
	</div>

	{#if store.graph.nodes.length > 0}
		<div class="minimap" aria-hidden="true">
			{#each store.graph.nodes as node (node.id)}
				{@const p = layout.pos.get(node.id)}
				{@const msx = mini.scale}
				<span class="m-node" style="left: {mini.offX + (p?.x ?? 0) * msx}px; top: {mini.offY + (p?.y ?? 0) * msx}px"></span>
			{/each}
			<span class="m-view" style="left: {mini.offX + mini.vx}px; top: {mini.offY + mini.vy}px; width: {mini.vw}px; height: {mini.vh}px"></span>
		</div>
	{/if}

	{#if store.graph.nodes.length === 0}
		<div class="empty mono">workflow JSON for {store.selectedSceneId ?? 'this scene'} is not loaded</div>
	{/if}
</div>

<style>
	.canvas {
		position: relative;
		flex: 1;
		min-height: 0;
		overflow: hidden;
		background-image: var(--canvas-grid);
		background-size: var(--canvas-grid-size) var(--canvas-grid-size);
		cursor: grab;
		touch-action: none;
	}
	.canvas:active {
		cursor: grabbing;
	}
	.edges {
		position: absolute;
		top: 0;
		left: 0;
		pointer-events: none;
	}
	.edge {
		fill: none;
		stroke: var(--border-strong);
		stroke-width: 1.5;
	}
	.world {
		position: absolute;
		top: 0;
		left: 0;
		transform-origin: 0 0;
		will-change: transform;
	}
	.minimap {
		position: absolute;
		right: 16px;
		bottom: 16px;
		width: 160px;
		height: 100px;
		background: var(--surface-2);
		border: 1px solid var(--border-default);
		border-radius: 4px;
		overflow: hidden;
		pointer-events: none;
	}
	.m-node {
		position: absolute;
		width: 2px;
		height: 2px;
		background: var(--surface-4);
	}
	.m-view {
		position: absolute;
		border: 1px solid var(--accent);
	}
	.empty {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 11px;
		color: var(--text-tertiary);
		pointer-events: none;
	}
</style>

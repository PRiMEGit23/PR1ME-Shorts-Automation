/**
 * Workflow store — Workflow Workbench slice (IMPLEMENTATION_PLAN 2S4):
 * 15-stage prompt chain, the 10-stage visual pipeline, per-scene ComfyUI
 * workflows with derived graphs, view toggle (Chain | Graph), and node
 * selection. Stores only apply state; the VM orchestrates (PRODUCT_LAYER §4).
 */

import type { BackendWorkflow } from '$lib/models/workflow';
import type { StageStatus } from '$lib/models/run';
import type { PromptStage, PipelineStage, PipelineStatus, WorkflowGraph } from '$lib/models/storyboard';
import { PIPELINE_ORDER, STAGE_ORDER } from '$lib/models/storyboard';
import type { SceneView } from '$lib/stores/storyboard.store';

export type WorkflowViewMode = 'chain' | 'graph';

export interface PipelineStageView {
	id: string;
	label: string;
	sub: string;
	status: PipelineStatus;
}

export const MIN_ZOOM = 0.5;
export const MAX_ZOOM = 2;
export const ZOOM_STEP = 0.25;

// ------------------------------------------------------- pure helpers

/** Map a report/backend status to the visual pipeline status set. */
export function mapStageStatus(status: string): PipelineStatus {
	switch (status) {
		case 'completed':
			return 'ok';
		case 'running':
			return 'running';
		case 'failed':
			return 'failed';
		case 'skipped':
			return 'skipped';
		default:
			return 'pending';
	}
}

/** The 15-stage chain in STAGE_ORDER with report data (pending defaults). */
export function chainFromBundle(stages: PromptStage[] | null | undefined): PromptStage[] {
	if (!stages || stages.length === 0) {
		return STAGE_ORDER.map((stageId) => ({
			stage_id: stageId,
			name: stageId,
			status: 'pending' as StageStatus,
			duration_ms: null,
			cache_hit: null,
			has_artifact: false,
			artifact: null
		}));
	}
	const byId = new Map(stages.map((s) => [s.stage_id, s]));
	return STAGE_ORDER.map((stageId) => byId.get(stageId) ?? {
		stage_id: stageId,
		name: stageId,
		status: 'pending' as StageStatus,
		duration_ms: null,
		cache_hit: null,
		has_artifact: false,
		artifact: null
	});
}

/** The 10-stage visual pipeline (IMPLEMENTATION_PLAN 2S4, UX §12). */
export function buildPipeline(
	stages: PromptStage[] | null | undefined,
	sceneViews: SceneView[],
	knowledgeRowFound: boolean
): PipelineStageView[] {
	const chain = chainFromBundle(stages);
	const byId = new Map(chain.map((s) => [s.stage_id, s]));
	const anyPassed = sceneViews.some((v) => v.candidates.some((c) => c.passed));
	const anyOptimized = sceneViews.some((v) => v.candidates.some((c) => c.hasOptimization));
	const anyWinner = sceneViews.some((v) => v.scene.image_path !== null);
	return PIPELINE_ORDER.map((stage: PipelineStage) => {
		let status: PipelineStatus = 'pending';
		if (stage.id === 'knowledge-base') {
			status = knowledgeRowFound ? 'ok' : mapStageStatus(byId.get(stage.source)?.status ?? 'pending');
		} else if (stage.id === 'qa') {
			status = anyPassed ? 'ok' : mapStageStatus(byId.get(stage.source)?.status ?? 'pending');
		} else if (stage.id === 'optimizer') {
			status = anyOptimized ? 'ok' : mapStageStatus(byId.get(stage.source)?.status ?? 'pending');
		} else if (stage.id === 'winner') {
			status = anyWinner ? 'ok' : mapStageStatus(byId.get(stage.source)?.status ?? 'pending');
		} else {
			status = mapStageStatus(byId.get(stage.source)?.status ?? 'pending');
		}
		return { id: stage.id, label: stage.label, sub: stage.sub, status };
	});
}

/** Format resolution `[1080, 1920]` → `1080×1920` (strings pass through). */
function formatResolution(resolution: [number, number] | string): string {
	if (Array.isArray(resolution)) return `${resolution[0]}×${resolution[1]}`;
	return String(resolution ?? '');
}

/**
 * Derive the graph from a BackendWorkflow — honest rendering of real
 * fields (UX §12): profile, sampler, scheduler, vae, loras, controlnet,
 * ip_adapter, upscaler, refiner, resolution, cfg/steps, prompts. No
 * invented topology; nodes absent from the JSON are omitted.
 */
export function deriveGraph(wf: BackendWorkflow | null | undefined): WorkflowGraph {
	const empty: WorkflowGraph = { nodes: [], edges: [] };
	if (!wf) return empty;
	const nodes: WorkflowGraph['nodes'] = [];
	const edges: WorkflowGraph['edges'] = [];
	const res = formatResolution(wf.resolution);

	const push = (
		id: string,
		label: string,
		layer: number,
		values: [string, string][]
	): void => {
		nodes.push({ id, label, layer, values });
	};

	if (wf.positive_prompt) {
		push('positive_prompt', 'positive_prompt', 0, [['prompt', wf.positive_prompt]]);
		edges.push({ from: 'positive_prompt', to: 'profile' });
	}
	if (wf.negative_prompt) {
		push('negative_prompt', 'negative_prompt', 0, [['prompt', wf.negative_prompt]]);
		edges.push({ from: 'negative_prompt', to: 'profile' });
	}
	if (wf.profile) {
		const values: [string, string][] = [['profile', wf.profile]];
		if (wf.cfg !== undefined) values.push(['cfg', String(wf.cfg)]);
		if (wf.steps !== undefined) values.push(['steps', String(wf.steps)]);
		if (res) values.push(['resolution', res]);
		if (wf.aspect_ratio) values.push(['aspect_ratio', wf.aspect_ratio]);
		push('profile', 'profile', 1, values);
	}
	if (wf.loras?.length) {
		push('loras', 'loras', 1, wf.loras.map((lora, i) => [String(i + 1), lora]));
		edges.push({ from: 'loras', to: 'sampler' });
	}
	if (wf.controlnet?.length) {
		push('controlnet', 'controlnet', 1, wf.controlnet.map((cn, i) => [String(i + 1), cn]));
		edges.push({ from: 'controlnet', to: 'sampler' });
	}
	if (wf.ip_adapter?.length) {
		push('ip_adapter', 'ip_adapter', 1, wf.ip_adapter.map((ip, i) => [String(i + 1), ip]));
		edges.push({ from: 'ip_adapter', to: 'sampler' });
	}
	if (wf.sampler) {
		const values: [string, string][] = [['sampler', wf.sampler]];
		if (wf.scheduler) values.push(['scheduler', wf.scheduler]);
		push('sampler', 'sampler', 2, values);
	}
	if (wf.upscaler) {
		push('upscaler', 'upscaler', 2, [['upscaler', wf.upscaler]]);
		edges.push({ from: 'upscaler', to: 'vae' });
	}
	if (wf.refiner) {
		push('refiner', 'refiner', 2, [['refiner', String(wf.refiner)]]);
		edges.push({ from: 'refiner', to: 'vae' });
	}
	if (wf.vae) {
		push('vae', 'vae', 3, [['vae', wf.vae]]);
	}
	if (nodes.length > 0 && !nodes.some((n) => n.id === 'vae')) {
		push('vae', 'vae', 3, [['vae', '—']]);
	}
	if (res) {
		push('output', 'OUTPUT', 4, [['resolution', res]]);
	}
	edges.push({ from: 'sampler', to: 'vae' });
	edges.push({ from: 'vae', to: 'output' });
	// drop edges referencing nodes we never created
	const ids = new Set(nodes.map((n) => n.id));
	return {
		nodes,
		edges: edges.filter((e) => ids.has(e.from) && ids.has(e.to))
	};
}

/** Scene ids selectable in the per-scene selector (S1..S5 + THUMB). */
export function sceneIds(views: SceneView[]): string[] {
	return views.map((v) => v.scene.scene_id);
}

// ------------------------------------------------------------- store

export class WorkflowStore {
	chain: PromptStage[] = $state([]);
	chainLoading = $state(false);
	chainError: string | null = $state(null);

	viewMode: WorkflowViewMode = $state('chain');
	/** Per-scene selector (S1..S5 + THUMB when present). */
	selectedSceneId: string | null = $state(null);
	/** Lazy per-scene workflow cache. */
	workflows: Map<string, BackendWorkflow> = $state(new Map());
	/** Selected chain stage (contract in the Inspector). */
	activeStageId: string | null = $state(null);

	selectedNodeIds: Set<string> = $state(new Set());
	zoom = $state(1);
	panX = $state(0);
	panY = $state(0);

	workflow = $derived(
		this.selectedSceneId ? this.workflows.get(this.selectedSceneId) ?? null : null
	);
	graph = $derived(deriveGraph(this.workflow));

	/** Injected by the VM: scene views + KB presence from the storyboard. */
	storyboardViews: SceneView[] = $state([]);
	knowledgeRowFound = $state(false);

	pipeline = $derived(
		buildPipeline(this.chain, this.storyboardViews, this.knowledgeRowFound)
	);

	activeStage = $derived(
		this.chain.find((s) => s.stage_id === this.activeStageId) ?? null
	);

	/* ------------------------------------------------- mutators */

	applyChain(stages: PromptStage[]): void {
		this.chain = chainFromBundle(stages);
		this.chainLoading = false;
		this.chainError = null;
		this.activeStageId = null;
	}

	setChainLoading(loading: boolean): void {
		this.chainLoading = loading;
	}

	setChainError(error: string | null): void {
		this.chainError = error;
		this.chainLoading = false;
	}

	selectScene(sceneId: string | null): void {
		this.selectedSceneId = sceneId;
		this.selectedNodeIds = new Set();
	}

	cacheWorkflow(sceneId: string, wf: BackendWorkflow): void {
		this.workflows = new Map(this.workflows).set(sceneId, wf);
	}

	toggleView(): void {
		this.viewMode = this.viewMode === 'chain' ? 'graph' : 'chain';
	}

	selectStage(stageId: string | null): void {
		this.activeStageId = stageId;
	}

	/** Click selects; Cmd+Click adds/toggles (UX §10 Workflow). */
	selectNode(nodeId: string | null, additive: boolean): void {
		if (nodeId === null) {
			this.selectedNodeIds = new Set();
			return;
		}
		const next = new Set(this.selectedNodeIds);
		if (additive) {
			if (next.has(nodeId)) {
				next.delete(nodeId);
			} else {
				next.add(nodeId);
			}
		} else {
			next.clear();
			next.add(nodeId);
		}
		this.selectedNodeIds = next;
	}

	clearSelection(): void {
		this.selectedNodeIds = new Set();
	}

	setZoom(zoom: number): void {
		this.zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
	}

	pan(dx: number, dy: number): void {
		this.panX += dx;
		this.panY += dy;
	}

	fitView(): void {
		this.zoom = 1;
		this.panX = 0;
		this.panY = 0;
	}
}

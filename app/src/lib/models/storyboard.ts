/**
 * Storyboard & Workflow models — mirror of run artifacts
 * (BACKEND_ARCHITECTURE §3/§4) + KB scene plan / prompt pack joins.
 * Contract: PRODUCT_LAYER_ARCHITECTURE §6 (load_storyboard / load_workflow /
 * load_prompt_chain / export_workflow).
 */

import type { ExecutionReport, RunManifest, StageStatus } from '$lib/models/run';
import type { RenderHistory } from '$lib/models/history';
import type { BackendWorkflow } from '$lib/models/workflow';

/** Fixed 15-stage pipeline order (BACKEND_ARCHITECTURE §3 — do not reorder). */
export const STAGE_ORDER: readonly string[] = [
	'knowledge_load',
	'educational_director',
	'ai_director',
	'visual_intelligence',
	'model_director',
	'prompt_compiler',
	'workflow_builder',
	'render_loop',
	'voice',
	'subtitles',
	'video_assembly',
	'video_render',
	'thumbnail',
	'metadata',
	'publisher'
] as const;

export interface StoryboardScene {
	scene_id: string;
	/** `images/<scene_id>.png` when the winner image exists (absolute path). */
	image_path: string | null;
	history: RenderHistory | null;
}

export interface StoryboardBundle {
	run_id: string;
	topic: string;
	run_dir: string;
	manifest: RunManifest;
	report: ExecutionReport | null;
	scenes: StoryboardScene[];
}

export interface PromptStage {
	stage_id: string;
	name: string;
	status: StageStatus;
	duration_ms: number | null;
	cache_hit: boolean | null;
	has_artifact: boolean;
	/** First `artifacts/<stage>/output.*.json` (stage contract). */
	artifact: unknown | null;
}

export interface PromptChainBundle {
	run_id: string;
	topic: string;
	stages: PromptStage[];
}

/** KB scene plan scene — 13 fields (BACKEND §7.2, `scene_plan_json`). */
export interface ScenePlan {
	scene_id: string;
	goal: string;
	teaching_point: string;
	camera: string;
	lens: string;
	composition: string;
	foreground: string;
	background: string;
	lighting: string;
	motion: string;
	objects: string;
	transition: string;
	duration: string;
}

export const SCENE_PLAN_FIELDS = [
	'scene_id',
	'goal',
	'teaching_point',
	'camera',
	'lens',
	'composition',
	'foreground',
	'background',
	'lighting',
	'motion',
	'objects',
	'transition',
	'duration'
] as const;

/** KB prompt pack shot — 9 fields (validate_knowledge_csv.py, §7.2). */
export interface PromptShot {
	shot_id: string;
	positive_prompt: string;
	negative_prompt: string;
	camera: string;
	lens: string;
	lighting: string;
	composition: string;
	style: string;
	render_notes: string;
}

export const PROMPT_SHOT_FIELDS = [
	'shot_id',
	'positive_prompt',
	'negative_prompt',
	'camera',
	'lens',
	'lighting',
	'composition',
	'style',
	'render_notes'
] as const;

/* ------------------------------------------------------ visual pipeline */

export type PipelineStatus = 'ok' | 'running' | 'pending' | 'failed' | 'skipped';

/** The 10-stage visual pipeline (IMPLEMENTATION_PLAN 2S4 Workflow). */
export interface PipelineStage {
	id: string;
	label: string;
	/** Backend stage id the status is sourced from (or 'knowledge'/'history'). */
	source: string;
	sub: string;
}

export const PIPELINE_ORDER: readonly PipelineStage[] = [
	{ id: 'knowledge-base', label: 'Knowledge Base', source: 'knowledge_load', sub: 'curated topics' },
	{ id: 'educational-director', label: 'Educational Director', source: 'educational_director', sub: 'learning plan' },
	{ id: 'ai-director', label: 'AI Director', source: 'ai_director', sub: 'shot directives' },
	{ id: 'storyboard', label: 'Storyboard', source: 'visual_intelligence', sub: 'scene plan' },
	{ id: 'prompt-compiler', label: 'Prompt Compiler', source: 'prompt_compiler', sub: 'prompt pack' },
	{ id: 'workflow-builder', label: 'Workflow Builder', source: 'workflow_builder', sub: 'comfyui graph' },
	{ id: 'comfyui-workflow', label: 'ComfyUI Workflow', source: 'render_loop', sub: 'render' },
	{ id: 'qa', label: 'QA', source: 'render_loop', sub: 'critics' },
	{ id: 'optimizer', label: 'Optimizer', source: 'render_loop', sub: 'repair' },
	{ id: 'winner', label: 'Winner', source: 'render_loop', sub: 'approved image' }
] as const;

/* ------------------------------------------------------------ workflow graph */

/** One derived graph node (UX_ARCHITECTURE §12 — honest field rendering). */
export interface GraphNode {
	id: string;
	label: string;
	layer: number;
	/** Rows rendered in the node body: [key, value][]. */
	values: [string, string][];
}

export interface GraphEdge {
	from: string;
	to: string;
}

export interface WorkflowGraph {
	nodes: GraphNode[];
	edges: GraphEdge[];
}

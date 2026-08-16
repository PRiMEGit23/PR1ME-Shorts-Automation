/**
 * BackendWorkflow model — mirror of `workflow/<scene_id>.json`.
 * Contract: BACKEND_ARCHITECTURE §4.5.
 */

export interface WorkflowNode {
	id: string;
	type?: string;
	label?: string;
	values?: Record<string, unknown>;
}

export interface BackendWorkflow {
	workflow_version: string;
	backend: string;
	profile: string;
	sampler: string;
	scheduler: string;
	steps: number;
	cfg: number;
	resolution: [number, number] | string;
	aspect_ratio: string;
	vae: string;
	loras: string[];
	negative_tokens: string[];
	positive_prompt: string;
	negative_prompt: string;
	controlnet: string[];
	ip_adapter: string[];
	depth_strategy?: string;
	segmentation_strategy?: string;
	upscaler: string;
	refiner?: string | null;
	animation_backend?: string;
	quality_target?: string;
	nodes: WorkflowNode[];
}
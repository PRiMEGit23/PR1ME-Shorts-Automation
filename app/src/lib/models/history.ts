/**
 * Render history model — mirror of `history/<topic>/<scene_id>/history.json`.
 * Contract: BACKEND_ARCHITECTURE §4.4.
 */

export type AttemptStatus =
	| 'rendered'
	| 'passed'
	| 'failed'
	| 'skipped_duplicate'
	| 'model_switched';

export interface QaReport {
	score?: number;
	passed?: boolean;
	issues?: string[];
	[rk: string]: unknown;
}

export interface RenderAttempt {
	attempt_id: string;
	index: number;
	status: AttemptStatus;
	scene_id: string;
	prompt: string;
	negative_prompt: string;
	workflow: Record<string, unknown>;
	workflow_profile: string;
	seed: number;
	fingerprint: string;
	image_sha256: string;
	image_model: string;
	image_path: string;
	qa_report: QaReport;
	optimization_report: Record<string, unknown>;
	rationale?: string | null;
}

export interface RenderHistory {
	topic: string;
	scene_id: string;
	seed: number;
	max_attempts: number;
	attempts: RenderAttempt[];
}
/**
 * Pipeline event model — mirror of `events.json`.
 * Contract: BACKEND_ARCHITECTURE §4.3.
 */

export type PipelineEventType =
	| 'pipeline_started'
	| 'pipeline_completed'
	| 'pipeline_failed'
	| 'stage_started'
	| 'stage_completed'
	| 'stage_failed'
	| 'stage_skipped'
	| 'checkpoint_saved'
	| 'resource_sample'
	| 'cache_hit';

export interface PipelineEvent {
	event_type: PipelineEventType;
	offset_ms: number;
	stage_id?: string | null;
	payload?: Record<string, unknown> | null;
}

export interface EventsFile {
	version: string;
	run_id: string;
	events: PipelineEvent[];
}
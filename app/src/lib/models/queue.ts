/**
 * Production OS queue models — mirror of `queue.json` exports.
 * Contract: BACKEND_ARCHITECTURE §6.
 */

export const JOB_STATUSES = [
	'pending',
	'running',
	'paused',
	'retry',
	'completed',
	'cancelled',
	'failed'
] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];

export const JOB_TYPES = [
	'storyboard',
	'render_image',
	'voice',
	'render_video',
	'metadata',
	'asset_index',
	'publish',
	'learning'
] as const;

export type JobType = (typeof JOB_TYPES)[number];

export interface JobView {
	job_id: string;
	project_id: string;
	topic: string;
	job_type: JobType;
	worker_type: string;
	status: JobStatus;
	priority: number;
	deadline_tick: number;
	estimated_runtime_ticks: number;
	start_tick?: number | null;
	end_tick?: number | null;
	retries: number;
}

export interface QueueSnapshot {
	version: string;
	total_jobs: number;
	status_counts: Record<JobStatus, number>;
	jobs: JobView[];
}
/**
 * Run models — mirror of `manifest.json`, `reports/execution_report.json`.
 * Contract: BACKEND_ARCHITECTURE §4.1 / §4.2.
 */

export type StageStatus = 'completed' | 'skipped' | 'failed' | 'pending' | 'running' | 'queued';

export interface StageRecord {
	stage_id: string;
	name?: string;
	version?: string;
	status: StageStatus;
	duration_ms?: number;
	cache_hit?: boolean;
	fingerprint?: string;
	memory_peak_mb?: number;
	gpu_time_ms?: number;
	metrics?: Record<string, unknown>;
	artifacts?: string[];
}

export interface RunManifest {
	version: string;
	run_id: string;
	job_id: string;
	topic: string;
	status: string;
	finished_at?: string | null;
	run_dir: string;
	error?: string | null;
	stages: StageRecord[];
	final_artifacts: Record<string, string>;
}

export interface ExecutionReport {
	version: string;
	run_id: string;
	job_id: string;
	topic: string;
	status: string;
	total_duration_ms: number;
	stages: StageRecord[];
	final_artifacts: Record<string, string>;
}

export interface RunSummary {
	run_id: string;
	topic: string;
	status: string;
	run_dir: string;
	started_at?: string | null;
	finished_at?: string | null;
}

export interface RunView {
	summary: RunSummary;
	manifest?: RunManifest | null;
	report?: ExecutionReport | null;
	/** true while a pr1me process is alive for this run */
	live: boolean;
}
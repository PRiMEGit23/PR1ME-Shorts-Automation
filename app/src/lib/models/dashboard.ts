/**
 * Production OS dashboard models — mirror of the six JSON exports.
 * Contract: BACKEND_ARCHITECTURE §6.
 */

import type { QueueSnapshot } from '$lib/models/queue';
import type { ProjectView } from '$lib/models/projects';

export interface ProductionReport {
	project_count: number;
	job_count: number;
	completed_jobs: number;
	failed_jobs: number;
	mean_qa: number;
	throughput_per_day: number;
	batch_counts: Record<string, number>;
	success_rate: number;
}

export interface DashboardExport {
	version: string;
	tick: number;
	project_count: number;
	job_count: number;
	completed: number;
	failed: number;
	mean_qa: number;
	throughput_per_day: number;
	batch_counts: Record<string, number>;
}

export interface DashboardView {
	production_report?: ProductionReport | null;
	dashboard?: DashboardExport | null;
	queue?: QueueSnapshot | null;
	projects?: ProjectView[] | null;
	workers?: WorkerStatistics | null;
	resources?: ResourceStatistics | null;
	/** simulation tick the exports were read at */
	tick: number;
}

export interface WorkerStatistics {
	version: string;
	workers: {
		worker_type: string;
		busy_ticks: number;
		idle_ticks: number;
		[key: string]: unknown;
	}[];
}

export interface ResourceStatistics {
	version: string;
	limits: Record<string, number>;
	history: unknown[];
	peak: { gpu_units: number; vram_mb: number; ram_mb: number; cpu_units: number; disk_mb: number };
}
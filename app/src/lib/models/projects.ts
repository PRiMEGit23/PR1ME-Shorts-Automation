/**
 * Project models — mirror of `projects.json` exports.
 * Contract: BACKEND_ARCHITECTURE §6.
 */

export interface ProjectView {
	project_id: string;
	topic: string;
	batch_kind: string;
	priority: number;
	deadline_tick: number;
	schedule_tick: number;
	knowledge_row_key: string;
	disk_budget_mb: number;
	job_ids: string[];
	stats: Record<string, unknown>;
	published: boolean;
}
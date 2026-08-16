/**
 * 2S5 Production Dashboard store — KPI derivation from IPC passthrough.
 * No duplicated calculations: all values are derived from
 * `production_stats` (6 export files) + `render_history` (per-run artifacts).
 * Slice of AppStore (PRODUCT_LAYER §5).
 */

import { derived, writable, get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import type {
	ProductionStats,
	HistoryRun,
	RenderProgress,
	RenderLogs,
	DashboardStats,
	QueueStatus,
	ActiveRun,
} from '$lib/models/render';

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------

function initialProductionStats(): ProductionStats {
	return {
		production_report: null,
		dashboard: null,
		queue: null,
		projects: null,
		worker_statistics: null,
		resource_statistics: null,
		tick: 0,
	};
}

function initialDashboardStats(): DashboardStats {
	return {
		successRate: 0,
		currentRenders: 0,
		queueLength: 0,
		avgRenderDuration: 0,
		ETA: null,
		todayCounts: { completed: 0, failed: 0, running: 0, cancelled: 0 },
		activeWorkers: 0,
		gpuInfo: null,
	};
}

// ---------------------------------------------------------------------------
// Public store
// ---------------------------------------------------------------------------

export interface DashboardStoreI {
	productionStats: Writable<ProductionStats>;
	stats: Writable<DashboardStats>;
	history: Writable<HistoryRun[]>;
	progress: Writable<RenderProgress | null>;
	logs: Writable<RenderLogs>;
	queueStatus: Writable<QueueStatus>;
	activeRun: Writable<ActiveRun | null>;

	// Actions
	loadStats: () => Promise<void>;
	loadHistory: () => Promise<void>;
	loadProgress: (runId: string) => Promise<void>;
	loadLogs: (runId: string, tail?: number) => Promise<void>;
	loadQueueStatus: () => Promise<void>;
	setActiveRun: (runId: string | null) => Promise<void>;
}

/** Create a new dashboard store with bridge injection. */
export function createDashboardStore(
	bridge: import('$lib/core/bridge').Bridge
): DashboardStoreI {
	const _p = writable<ProductionStats>(initialProductionStats());
	const _s = writable<DashboardStats>(initialDashboardStats());
	const _h = writable<HistoryRun[]>([]);
	const _prog = writable<RenderProgress | null>(null);
	const _log = writable<RenderLogs>({ lines: [] });
	const _qs = writable<QueueStatus>({ active: [], tick: 0 });
	const _ar = writable<ActiveRun | null>(null);

	return {
		productionStats: _p,
		stats: _s,
		history: _h,
		progress: _prog,
		logs: _log,
		queueStatus: _qs,
		activeRun: _ar,

		// -------- loaders --------

		async loadStats(): Promise<void> {
			const ps = await bridge.production_stats();
			_p.set(ps);
			// Derive KPIs from the six export files
			const s = deriveKpis(ps, get(this.history));
			_s.set(s);
		},

		async loadHistory(): Promise<void> {
			const h = await bridge.render_history();
			_h.set(h as HistoryRun[]);
			// Re-derive KPIs when history changes
			const s = deriveKpis(get(this.productionStats), h as HistoryRun[]);
			_s.set(s);
		},

		async loadProgress(runId: string): Promise<void> {
			const prog = await bridge.render_progress(runId);
			_prog.set(prog);
		},

		async loadLogs(runId: string, tail: number = 50): Promise<void> {
			const lg = await bridge.render_logs(runId, tail);
			_log.set(lg);
		},

		async loadQueueStatus(): Promise<void> {
			const qs = await bridge.queue_status();
			_qs.set(qs);
		},

		// -------- inspector --------

		setActiveRun(runId: string | null): Promise<void> {
			if (runId === null) {
				_ar.set(null);
				return Promise.resolve();
			}
			// Find the run in history + fetch its manifest+report via render_progress
			// For now, just hold the run_id; the inspector VM will load details
			const hist = get(this.history).find((r) => r.run_id === runId);
			if (hist) {
				// launch progress load + derive active run metadata
				this.loadProgress(runId).then(() => {
					const prog = get(this.progress);
					if (prog && prog.topic) {
						_ar.set({
							run_id: prog.run_id,
							topic: prog.topic,
							process_id: 0, // placeholder — populated by supervisor
							started_at: new Date().getTime(),
						});
					} else {
						_ar.set(null);
					}
				});
			} else {
				_ar.set(null);
			}
			return Promise.resolve();
		},
	} as DashboardStoreI;
}

// ---------------------------------------------------------------------------
// KPI derivation — pure functions, no side effects
// ---------------------------------------------------------------------------

/** Derive DashboardStats from ProductionStats + HistoryRun[].
 * Called whenever either source changes.
 */

function deriveKpis(
	ps: ProductionStats,
	history: HistoryRun[]
): DashboardStats {
	const total = history.length;
	const completed = history.filter((r) => r.status === 'completed').length;
	const failed = history.filter((r) => r.status === 'failed').length;
	const running = history.filter((r) => r.status === 'running').length;
	const cancelled = history.filter((r) => r.status === 'cancelled').length;

	const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;
	const avgDuration =
		completed > 0
			? history
					.filter((r) => r.total_duration_ms && r.total_duration_ms > 0)
					.reduce((sum, r) => sum + r.total_duration_ms!, 0) /
					completed
			: 0;

	// Today counts — use finished_at date-only comparison (simplified)
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	const todayCounts = {
		completed: history.filter(
			(r) => r.finished_at && new Date(r.finished_at).setHours(0, 0, 0, 0) === today.setHours(0, 0, 0, 0)
		).length,
		failed: history.filter(
			(r) => r.status === 'failed'
		).length,
		running,
		cancelled,
	};

	// ETA: estimate minutes until queue clear based on remaining + avg duration
	const remaining = history.filter((r) => r.status !== 'completed').length;
	const ms = avgDuration * remaining;
	const etaMin = Math.max(1, Math.round(ms / 60000));

	// Active workers + GPU info from production_stats dashboard export if available
	let activeWorkers = 0;
	let gpuInfo: { units: number; vram_mb: number } | null = null;
	if (ps.dashboard && typeof ps.dashboard === 'object') {
		const d = ps.dashboard as Record<string, unknown>;
		activeWorkers = typeof d.active_workers === 'number' ? d.active_workers : 0;
		gpuInfo = typeof d.gpu_units === 'number' ? { units: d.gpu_units, vram_mb: (d.vram_mb ?? 0) as number } : null;
	}

	return {
		successRate,
		currentRenders: running,
		queueLength: total,
		avgRenderDuration: avgDuration,
		ETA: etaMin,
		todayCounts,
		activeWorkers,
		gpuInfo,
	};
}

// ---------------------------------------------------------------------------
// Export the store (singleton per bridge instance)
// ---------------------------------------------------------------------------

export const dashboardStore = createDashboardStore({} as any); // bridge injected by caller
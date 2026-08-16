/**
 * 2S5 Render Queue ViewModel — presentation only.
 * Orchestrates the Render Workbench (IMPLEMENTATION_PLAN 2S5):
 * modes Board | Dashboard | History, event subscriptions, job actions,
 * queue picking, and toast notifications (PRODUCT_LAYER §6/§9).
 * Views call actions; actions call services; stores apply results.
 */

import { derived, writable, get } from 'svelte/store';
import type { Bridge } from '$lib/core/bridge';
import type {
	QueueStatus,
	HistoryRun,
	RenderProgress,
	RenderLogs,
	ProductionStats,
	QueueItem,
	DashboardStats,
	ActiveRun,
} from '$lib/models/render';
import { UiStore, pushToast } from '$lib/stores/ui.store';
import { queueStore } from '$lib/stores/queue.store';
import { dashboardStore } from '$lib/stores/dashboard.store';

export class RenderVm {
	public mode = 'board' as 'board' | 'dashboard' | 'history';
	public selectedRunId: string | null = null;
	public isPaused = false;
	public showInspector = false;
	public showLogs = false;
	public logScrollBottom = true;
	public bridge: Bridge;

	private _historyUnsub: (() => void) | null = null;
	private _queueStatusUnsub: (() => void) | null = null;
	private _progressUnsub: (() => void) | null = null;
	private _logsUnsub: (() => void) | null = null;
	private _dispose: (() => void) | null = null;

	constructor(ui: UiStore, bridge: Bridge) {
		this._dispose = () => {};
		this.bridge = bridge;
		this.syncAll();
	}

	private async syncAll(): Promise<void> {
		await Promise.all([
			this.bridge.queue_status(),
			this.bridge.render_history(),
			this.bridge.production_stats(),
		]);
		this.wireSubscriptions();
	}

	private wireSubscriptions(): void {
		// History changes → re-derive KPIs
		this._historyUnsub = queueStore.subscribe(() => {
			dashboardStore.loadHistory();
		});

		// Queue status from Rust
		this._queueStatusUnsub = queueStore.subscribe(() => {
			// UI updates via derived computed values
		});

		// Progress for selected run
		this._progressUnsub = queueStore.subscribe(() => {
			// UI re-renders via $derived when items change
		});

		// Logs for selected run
		const linesStore = $derived(
			get(queueStore).items.length > 0 ? 'has items' : 'empty'
		);
	}

	// -------- selection / inspector --------

	public selectRun(runId: string): void {
		this.selectedRunId = runId;
		this.showInspector = true;
		dashboardStore.setActiveRun(runId);
	}

	public closeInspector(): void {
		this.showInspector = false;
		this.selectedRunId = null;
		dashboardStore.setActiveRun(null);
	}

	// -------- progress / logs --------

	public refreshProgress(runId: string): void {
		this.bridge.render_progress(runId);
	}

	public refreshLogs(runId: string, tail: number = 50): void {
		this.bridge.render_logs(runId, tail);
	}

	// -------- job actions --------

	public async retryRender(): Promise<void> {
		if (!this.selectedRunId) return;
		const seed = 42;
		const result = await this.bridge.retry_render(this.selectedRunId, seed);
		if (result.ok) {
			pushToast('info', 'Retry started', {
				message: `Resuming render for ${this.selectedRunId}`,
			});
			const qs = get(queueStore);
			const item = qs.items.find((i) => i.id === this.selectedRunId);
			if (item) item.status = 'retrying';
			queueStore.set({ ...qs, items: [...qs.items] });
		}
	}

	public async cancelRender(): Promise<void> {
		if (!this.selectedRunId) return;
		const result = await this.bridge.cancel_render(this.selectedRunId);
		if (result.ok) {
			pushToast('error', 'Render cancelled', {
				message: `Job aborted for ${this.selectedRunId}`,
			});
			const qs = get(queueStore);
			const item = qs.items.find((i) => i.id === this.selectedRunId);
			if (item) {
				item.status = 'cancelled';
				item.error = 'job_aborted';
				item.finishedAt = new Date().toISOString();
			}
			queueStore.set({ ...qs, items: [...qs.items] });
			this.closeInspector();
		}
	}

	public async resumeRender(): Promise<void> {
		if (!this.selectedRunId) return;
		const args = {
			run_dir: '',
			topic: '',
			seed: 42,
			max_attempts: 3,
			publish: false,
		};
		const result = await this.bridge.resume_render(args);
		if (result.ok) {
			pushToast('info', 'Resume started', {
				message: `Resuming render for ${this.selectedRunId}`,
			});
		}
	}

	// -------- open folder --------

	public async openOutputFolder(): Promise<void> {
		if (!this.selectedRunId) return;
		const result = await this.bridge.open_output_folder(this.selectedRunId);
		if (result.ok) {
			pushToast('info', 'Folder opened', {
				message: `Output folder for ${this.selectedRunId}`,
			});
		}
	}

	// -------- mode toggle --------

	public setMode(mode: 'board' | 'dashboard' | 'history'): void {
		this.mode = mode;
	}

	// -------- queue from script --------

	public queueFromScript(topics: string[]): void {
		for (const topic of topics) {
			const newId = `q-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
			const newItem: QueueItem = {
				id: newId,
				topic,
				slug: topic.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'untitled',
				seed: 42,
				maxAttempts: 3,
				publish: false,
				status: 'pending',
				runId: null,
				runDir: null,
				batchId: '',
				position: get(queueStore).items.length,
				stageStates: {},
				stageOrder: [],
				overallPct: 0,
				currentStage: null,
				stageProgress: null,
				etaMs: null,
				runtimeMs: 0,
				retries: 0,
				thumbnails: [],
				logLines: [],
				error: null,
				durationMs: null,
				finishedAt: null,
			};
			const qs = get(queueStore);
			queueStore.set({ ...qs, items: [...qs.items, newItem] });
			pushToast('info', 'Queue item added', {
				message: `Added ${topic} to render queue`,
			});
		}
		// re-derive KPIs after adding items
		dashboardStore.loadStats();
	}

	// -------- lifecycle --------

	public onDestroy(): void {
		if (this._historyUnsub) this._historyUnsub();
		if (this._queueStatusUnsub) this._queueStatusUnsub();
		if (this._progressUnsub) this._progressUnsub();
		if (this._logsUnsub) this._logsUnsub();
		if (this._dispose) this._dispose();
	}
}
/**
 * Typed IPC facade (PRODUCT_LAYER_ARCHITECTURE §6).
 * The ONLY way the frontend talks to Rust. Injectable transport keeps
 * ViewModels/Services unit-testable without Tauri.
 */

import { invoke } from '@tauri-apps/api/core';

import type { SettingsModel } from '$lib/models/settings';
import type { HealthState, ProviderId } from '$lib/models/providers';
import type { RunManifest, RunSummary, ExecutionReport } from '$lib/models/run';
import type { PipelineEvent } from '$lib/models/events';
import type { BackendWorkflow } from '$lib/models/workflow';
import type { RenderHistory } from '$lib/models/history';
import type { QueueSnapshot } from '$lib/models/queue';
import type { DashboardView } from '$lib/models/dashboard';
import type {
	ProductionCreateArgs,
	ProductionModel,
	ProductionSummary
} from '$lib/models/productions';
import type { KnowledgeRow, ValidationReport } from '$lib/models/knowledge';
import type { LayoutState } from '$lib/stores/layout.store';
import type { WorkbenchId } from '$lib/stores/ui.store';

export type IpcTransport = (cmd: string, args: unknown) => Promise<unknown>;

/** Error payloads are `code: message` strings (PRODUCT_LAYER §6). */
export class BridgeError extends Error {
	constructor(
		public readonly code: string,
		message: string
	) {
		super(message);
		this.name = 'BridgeError';
	}
}

const tauriTransport: IpcTransport = (cmd, args) => invoke(cmd, args as Record<string, unknown>);

export interface OkPayload {
	ok: boolean;
}

export interface EnvProbeResult {
	value: string | null;
}

export interface AppVersion {
	version: string;
	platform: string;
	arch: string;
	pr1me_version: string;
}

export interface FsEntry {
	path: string;
	name: string;
	kind: 'file' | 'dir';
	size?: number | null;
	modified?: string | null;
}

export interface RunEventsResult {
	events: PipelineEvent[];
}

export class Bridge {
	constructor(private readonly transport: IpcTransport = tauriTransport) {}

	private async invoke<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
		try {
			return (await this.transport(cmd, args)) as T;
		} catch (err) {
			const raw = err instanceof Error ? err.message : String(err);
			const [code, ...rest] = raw.split(': ');
			throw new BridgeError(code ?? 'unknown', rest.join(': ') || raw);
		}
	}

	/* ---------- 2S1 commands ---------- */

	app_version(): Promise<AppVersion> {
		return this.invoke<AppVersion>('app_version');
	}

	settings_load(): Promise<SettingsModel> {
		return this.invoke<SettingsModel>('settings_load');
	}

	settings_save(model: SettingsModel): Promise<OkPayload> {
		return this.invoke<OkPayload>('settings_save', { model });
	}

	env_probe(name: string): Promise<EnvProbeResult> {
		return this.invoke<EnvProbeResult>('env_probe', { name });
	}

	layout_save(workbench: WorkbenchId, layout: LayoutState): Promise<OkPayload> {
		return this.invoke<OkPayload>('layout_save', { workbench, layout });
	}

	/* ---------- 2S2: providers & productions ---------- */

	providers_health(provider: ProviderId): Promise<HealthState> {
		return this.invoke<HealthState>('providers_health', { provider });
	}

	providers_health_all(): Promise<HealthState[]> {
		return this.invoke<HealthState[]>('providers_health_all');
	}

	production_list(): Promise<ProductionSummary[]> {
		return this.invoke<ProductionSummary[]>('production_list');
	}

	production_create(args: ProductionCreateArgs): Promise<ProductionModel> {
		return this.invoke<ProductionModel>('production_create', { args });
	}

	production_load(productionId: string): Promise<ProductionModel> {
		return this.invoke<ProductionModel>('production_load', { productionId });
	}

	production_save(model: ProductionModel): Promise<OkPayload> {
		return this.invoke<OkPayload>('production_save', { model });
	}

	production_import(name: string): Promise<ProductionModel> {
		return this.invoke<ProductionModel>('production_import', { name });
	}

	/* ---------- 2S3: knowledge ---------- */

	csv_read(path: string, offset: number, limit: number): Promise<{ header: string[]; rows: string[][]; total: number }> {
		return this.invoke('csv_read', { path, offset, limit });
	}

	csv_write(path: string, header: string[], rows: string[][]): Promise<OkPayload> {
		return this.invoke<OkPayload>('csv_write', { path, header, rows });
	}

	csv_validate(path: string): Promise<ValidationReport> {
		return this.invoke<ValidationReport>('csv_validate', { path });
	}

	/* ---------- 2S4: generate & runs ---------- */

	run_list(): Promise<RunSummary[]> {
		return this.invoke<RunSummary[]>('run_list');
	}

	run_manifest(runId: string): Promise<RunManifest> {
		return this.invoke<RunManifest>('run_manifest', { runId });
	}

	run_report(runId: string): Promise<ExecutionReport> {
		return this.invoke<ExecutionReport>('run_report', { runId });
	}

	run_events(runId: string): Promise<RunEventsResult> {
		return this.invoke<RunEventsResult>('run_events', { runId });
	}

	run_history(runId: string, sceneId: string): Promise<RenderHistory> {
		return this.invoke<RenderHistory>('run_history', { runId, sceneId });
	}

	workflow_read(runId: string, sceneId: string): Promise<BackendWorkflow> {
		return this.invoke<BackendWorkflow>('workflow_read', { runId, sceneId });
	}

	process_logs(runId: string, tail: number): Promise<{ lines: string[] }> {
		return this.invoke<{ lines: string[] }>('process_logs', { runId, tail });
	}

	export_dashboard(ticks?: number): Promise<DashboardView> {
		return this.invoke<DashboardView>('export_dashboard', { ticks });
	}

	/* ---------- 2S5: fs, edit, multi-monitor ---------- */

	fs_tree(path: string, maxDepth: number, includeHidden: boolean): Promise<FsEntry[]> {
		return this.invoke<FsEntry[]>('fs_tree', { path, maxDepth, includeHidden });
	}

	fs_read_text(path: string): Promise<{ content: string }> {
		return this.invoke<{ content: string }>('fs_read_text', { path });
	}

	image_open(path: string): Promise<OkPayload> {
		return this.invoke<OkPayload>('image_open', { path });
	}

	window_detach(panelId: string): Promise<{ windowLabel: string }> {
		return this.invoke<{ windowLabel: string }>('window_detach', { panelId });
	}

	/* ---------- 2S6: updater ---------- */

	updater_check(): Promise<{ version?: string } | null> {
		return this.invoke<{ version?: string } | null>('updater_check');
	}

	/** Raw invoke for commands added after this facade ships. */
	raw<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
		return this.invoke<T>(cmd, args);
	}
}
/**
 * Workflow VM — orchestrates the Workflow Workbench (IMPLEMENTATION_PLAN
 * 2S4): prompt chain, the 10-stage visual pipeline, per-scene ComfyUI
 * workflow graphs (zoom/pan/fit/minimap/multi-select), JSON export + copy,
 * and chain/graph selection for the Inspector.
 */

import { save } from '@tauri-apps/plugin-dialog';

import type { AppServices } from '$lib/core/di';
import type { UiStore } from '$lib/stores/ui.store';
import { sceneIds, type WorkflowStore } from '$lib/stores/workflow.store';
import type { StoryboardStore } from '$lib/stores/storyboard.store';

export class WorkflowVm {
	constructor(
		private readonly ui: UiStore,
		private readonly storyboard: StoryboardStore,
		private readonly store: WorkflowStore,
		private readonly services: AppServices
	) {}

	/** Sync storyboard context, then load the chain + first scene graph. */
	async open(runId?: string): Promise<void> {
		this.store.storyboardViews = this.storyboard.sceneViews;
		this.store.knowledgeRowFound = this.storyboard.knowledgeRow !== null;
		await this.loadChain(runId);
		const ids = sceneIds(this.store.storyboardViews);
		const current = this.store.selectedSceneId ?? ids[0] ?? null;
		this.store.selectScene(current);
		if (current) await this.loadWorkflow(current);
	}

	async loadChain(runId?: string): Promise<void> {
		if (this.store.chainLoading) return;
		this.store.setChainLoading(true);
		this.store.setChainError(null);
		try {
			const bundle = await this.services.storyboard.loadPromptChain(runId);
			this.store.applyChain(bundle.stages);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.store.setChainError(message);
			this.ui.pushToast('error', 'Prompt chain not loaded', { message });
		}
	}

	/** Select a scene and lazily load its workflow (cache + guard). */
	async selectScene(sceneId: string): Promise<void> {
		this.store.selectScene(sceneId);
		this.store.selectStage(null);
		if (!this.store.workflows.has(sceneId)) {
			await this.loadWorkflow(sceneId);
		}
	}

	async loadWorkflow(sceneId: string): Promise<void> {
		const bundle = this.storyboard.bundle;
		if (!bundle) return;
		try {
			const wf = await this.services.storyboard.loadWorkflow(bundle.run_id, sceneId);
			this.store.cacheWorkflow(sceneId, wf);
		} catch (err) {
			this.ui.pushToast('error', `Workflow S${sceneId} not loaded`, {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}

	/** `1`/`2` — Chain | Graph toggle (UX §10 Workflow). */
	toggleView(): void {
		this.store.toggleView();
	}

	selectStage(stageId: string | null): void {
		this.store.selectStage(stageId);
	}

	/** Click selects; Cmd/Ctrl+Click multi-select; Del clears (UX §10). */
	selectNode(nodeId: string | null, additive: boolean): void {
		this.store.selectNode(nodeId, additive);
	}

	clearSelection(): void {
		this.store.clearSelection();
	}

	zoomIn(): void {
		this.store.setZoom(this.store.zoom + 0.25);
	}

	zoomOut(): void {
		this.store.setZoom(this.store.zoom - 0.25);
	}

	/** `W` fit graph (UX §10 Workflow). */
	fit(): void {
		this.store.fitView();
	}

	pan(dx: number, dy: number): void {
		this.store.pan(dx, dy);
	}

	/** Export the current scene's workflow JSON (OS save dialog). */
	async exportJson(): Promise<void> {
		const bundle = this.storyboard.bundle;
		const sceneId = this.store.selectedSceneId;
		if (!bundle || !sceneId || !this.store.workflow) return;
		if (!('__TAURI_INTERNALS__' in window)) {
			this.ui.pushToast('info', 'Export unavailable', {
				message: 'OS save dialogs require the desktop app.'
			});
			return;
		}
		const picked = await save({
			filters: [{ name: 'Workflow JSON', extensions: ['json'] }],
			defaultPath: `${sceneId}.workflow.json`
		});
		if (!picked) return;
		try {
			await this.services.storyboard.exportWorkflow(bundle.run_id, sceneId, picked);
			this.ui.pushToast('success', 'Workflow exported', { message: picked });
		} catch (err) {
			this.ui.pushToast('error', 'Export failed', {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}

	/** Copy the current scene's workflow JSON to the clipboard. */
	async copyJson(): Promise<void> {
		const wf = this.store.workflow;
		if (!wf) return;
		try {
			await navigator.clipboard.writeText(JSON.stringify(wf, null, 2));
			this.ui.pushToast('success', 'Workflow copied', {
				message: 'JSON is on the clipboard.'
			});
		} catch (err) {
			this.ui.pushToast('error', 'Copy failed', {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}
}

/**
 * Storyboard VM — orchestrates the Storyboard Workbench (IMPLEMENTATION_PLAN
 * 2S4): load the latest run (or a specific one), scene selection + keyboard
 * navigation, canvas zoom/pan/fit, and preview-only approvals. Views call
 * actions; actions call services; stores apply results (PRODUCT_LAYER §4).
 */

import type { AppServices } from '$lib/core/di';
import type { UiStore } from '$lib/stores/ui.store';
import type { KnowledgeStore } from '$lib/stores/knowledge.store';
import { neighborSceneId, type StoryboardStore } from '$lib/stores/storyboard.store';

export class StoryboardVm {
	constructor(
		private readonly ui: UiStore,
		private readonly knowledge: KnowledgeStore,
		private readonly store: StoryboardStore,
		private readonly services: AppServices
	) {}

	/** Load the latest run (or `runId`); selects the first scene. */
	async open(runId?: string): Promise<void> {
		if (this.store.loading) return;
		this.store.setLoading(true);
		this.store.setError(null);
		try {
			const bundle = await this.services.storyboard.loadStoryboard(runId);
			this.store.applyBundle(bundle, this.knowledge.allRows);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.store.setError(message);
			this.ui.pushToast('error', 'Storyboard not loaded', { message });
		}
	}

	selectScene(sceneId: string | null): void {
		this.store.selectScene(sceneId);
	}

	/** N/P or ←/→ — wrap-around scene navigation (UX §10 Storyboard). */
	stepScene(dir: 1 | -1): void {
		const ids = this.store.sceneViews.map((v) => v.scene.scene_id);
		this.store.selectScene(neighborSceneId(ids, this.store.selectedSceneId, dir));
	}

	/** Preview-only approve override (never persisted — UX §11). */
	approve(sceneId: string, attemptId: string | null): void {
		this.store.approveCandidate(sceneId, attemptId);
	}

	zoomIn(): void {
		this.store.setZoom(this.store.zoom + 0.25);
	}

	zoomOut(): void {
		this.store.setZoom(this.store.zoom - 0.25);
	}

	/** `+`/`-` zoom, `F` fit, `Space` reset pan. */
	zoom(delta: number): void {
		this.store.setZoom(this.store.zoom + delta);
	}

	fit(): void {
		this.store.fitView();
	}

	pan(dx: number, dy: number): void {
		this.store.pan(dx, dy);
	}
}

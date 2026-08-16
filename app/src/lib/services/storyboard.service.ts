/**
 * Storyboard service — loads run artifacts through the bridge
 * (PRODUCT_LAYER §4: ViewModels call services, never Tauri).
 */

import type { Bridge } from '$lib/core/bridge';
import type { BackendWorkflow } from '$lib/models/workflow';
import type { StoryboardBundle, PromptChainBundle } from '$lib/models/storyboard';

export class StoryboardService {
	constructor(private readonly bridge: Bridge) {}

	/** Latest run when `runId` is omitted. */
	loadStoryboard(runId?: string): Promise<StoryboardBundle> {
		return this.bridge.load_storyboard(runId);
	}

	loadWorkflow(runId: string, sceneId: string): Promise<BackendWorkflow> {
		return this.bridge.load_workflow(runId, sceneId);
	}

	loadPromptChain(runId?: string): Promise<PromptChainBundle> {
		return this.bridge.load_prompt_chain(runId);
	}

	exportWorkflow(runId: string, sceneId: string, path: string): Promise<{ ok: boolean }> {
		return this.bridge.export_workflow(runId, sceneId, path);
	}
}

<script lang="ts">
	/**
	 * ProgressRail — horizontal progress bar showing 15-stage pipeline progress.
	 * Uses the 15-stage pipeline order from the backend.
	 */
import type { Bridge } from '$lib/core/bridge';
import Button from '$lib/components/primitives/Button.svelte';

	const bridge = {} as Bridge;

	let { pct = 0, stages = 15 } = $props();

// Compute which stages are completed vs pending
	const completedStages = $derived(
		Math.round((pct / 100) * stages)
	);
	const pendingStages = $derived(stages - completedStages);

	// STAGE_ORDER from backend (first 15 mission stages)
	const stageOrder = [
		'knowledge_load',
		'educational_director',
		'ai_director',
		'visual_intelligence',
		'model_director',
		'prompt_compiler',
		'workflow_builder',
		'render_loop',
		'voice',
		'subtitles',
		'video_assembly',
		'video_render',
		'thumbnail',
		'metadata',
		'publisher',
	];

	let stageNames = $derived(stageOrder);
</script>

<div class="progress-rail" style="--pct: {pct}; --stages: {stages};">
	<div class="progress-track">
		{#each stageOrder as stage, i}
			<div
				class="progress-stage {completedStages > i ? 'completed' : 'pending'}"
				title={stage}
			>
				<div class="stage-fill">
					{completedStages > i ? '●' : '○'}
				</div>
			</div>
		{/each}
	</div>
	<div class="progress-percentage">
		{Math.round(pct)}%
	</div>
</div>
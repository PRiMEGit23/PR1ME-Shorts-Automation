<script lang="ts">
	/**
	 * PromptChain — the 15-stage vertical rail (UX §12). Clicking a stage
	 * opens its contract (artifacts/<stage>/output.*.json) in the Inspector.
	 */
	import ChainNode from '$lib/components/domain/ChainNode.svelte';
	import type { PromptStage } from '$lib/models/storyboard';
	import type { WorkflowVm } from '$lib/viewmodels/workflow.vm';

	let {
		stages,
		activeStageId,
		vm
	}: {
		stages: PromptStage[];
		activeStageId: string | null;
		vm: WorkflowVm;
	} = $props();
</script>

<div class="chain" role="listbox" aria-label="Prompt chain (15 stages)">
	{#each stages as stage, index (stage.stage_id)}
		<ChainNode
			{stage}
			{index}
			selected={stage.stage_id === activeStageId}
			onselect={() => vm.selectStage(stage.stage_id === activeStageId ? null : stage.stage_id)}
		/>
		{#if index < stages.length - 1}
			<span class="conn" aria-hidden="true"></span>
		{/if}
	{/each}
</div>

<style>
	.chain {
		display: flex;
		flex-direction: column;
		gap: 2px;
		overflow-y: auto;
	}
	.conn {
		width: 1px;
		height: 8px;
		margin-left: 27px;
		background: var(--border-subtle);
		flex-shrink: 0;
	}
</style>

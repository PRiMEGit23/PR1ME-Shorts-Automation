<script lang="ts">
	/**
	 * Workbench host — single route (UX §1): per-workbench views. 2S1
	 * renders documented empty states + action affordances for later phases.
	 */
	import EmptyState from '$lib/components/layout/EmptyState.svelte';
	import Button from '$lib/components/primitives/Button.svelte';
	import KnowledgeGallery from '$lib/components/domain/KnowledgeGallery.svelte';
	import KnowledgeEditor from '$lib/components/domain/KnowledgeEditor.svelte';
	import StoryboardBoard from '$lib/components/domain/StoryboardBoard.svelte';
	import WorkflowBoard from '$lib/components/domain/WorkflowBoard.svelte';
	import { store } from '../main';
	import { workbenchById } from '$lib/stores/ui.store';

	const wb = $derived(workbenchById(store.ui.workbench));
	const scriptEditorOpen = $derived(
		wb.id === 'script' && store.knowledge.editor.open && store.script !== null
	);
	const immersive = $derived(wb.id === 'storyboard' || wb.id === 'workflow');
</script>

<div class="host" class:canvas={wb.id === 'storyboard' || wb.id === 'workflow'}>
	{#key wb.id}
		<div class="wb-view">
			{#if !scriptEditorOpen && !immersive}
				<header class="host-head">
					<span class="h-title label">{wb.label}</span>
					<span class="h-sub mono">{wb.purpose}</span>
				</header>
			{/if}

			{#if wb.id === 'library'}
				<EmptyState
					icon="library"
					title="Welcome to PR1ME Studio"
					subtitle="Create a production to get started — productions own their .env, knowledge base, and run artifacts."
				>
					{#snippet children()}
						<Button variant="secondary" icon="plus" title="Production creation arrives with 2S2" disabled>
							New Production
						</Button>
					{/snippet}
				</EmptyState>
			{:else if wb.id === 'script' && store.script}
				{#if scriptEditorOpen}
					<KnowledgeEditor ui={store.ui} store={store.knowledge} vm={store.script} />
				{:else}
					<KnowledgeGallery ui={store.ui} store={store.knowledge} vm={store.script} />
				{/if}
			{:else if wb.id === 'script'}
				<EmptyState
					icon="script"
					title="Script"
					subtitle="Pick a topic from the knowledge base (2S3)."
				/>
			{:else if wb.id === 'storyboard' && store.storyboardVm}
				<StoryboardBoard ui={store.ui} store={store.storyboard} vm={store.storyboardVm} />
			{:else if wb.id === 'storyboard'}
				<EmptyState
					icon="storyboard"
					title="Storyboard"
					subtitle="Approved candidates will board here after generation (2S4)."
				/>
			{:else if wb.id === 'workflow' && store.workflowVm}
				<WorkflowBoard store={store.workflow} vm={store.workflowVm} />
			{:else if wb.id === 'workflow'}
				<EmptyState
					icon="workflow"
					title="Workflow"
					subtitle="The prompt chain and ComfyUI graph will render here (2S4)."
				/>
			{:else if wb.id === 'render'}
				<EmptyState
					icon="render"
					title="Nothing rendering. Queue episodes from Script."
					subtitle="Render progress streams here live during runs (2S4)."
				>
					{#snippet children()}
						<Button variant="secondary" icon="play" title="Run orchestration arrives with 2S4" disabled>
							Queue Episode
						</Button>
					{/snippet}
				</EmptyState>
			{:else if wb.id === 'edit'}
				<EmptyState
					icon="edit"
					title="Edit"
					subtitle="The timeline and player will live here once render outputs exist (2S5)."
				/>
			{:else if wb.id === 'deliver'}
				<EmptyState
					icon="deliver"
					title="Deliver"
					subtitle="Publish targets and metadata review will appear here (2S5)."
				/>
			{:else if wb.id === 'insights'}
				<EmptyState
					icon="insights"
					title="Insights"
					subtitle="Analytics and learning proposals will appear here (2S6)."
				/>
			{/if}
		</div>
	{/key}
</div>

<style>
	.host {
		position: relative;
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
		min-height: 0;
		overflow: auto;
		background: var(--surface-0);
	}
	.host.canvas {
		background-image: var(--canvas-grid);
		background-size: var(--canvas-grid-size) var(--canvas-grid-size);
	}
	.wb-view {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
		animation: wb-in var(--dur-slow) var(--ease-out) both;
	}
	.wb-view .host-head {
		animation-delay: 30ms;
	}
	@keyframes wb-in {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
	.host-head {
		display: flex;
		align-items: baseline;
		gap: var(--space-3);
		padding: var(--space-4) var(--space-5);
		border-bottom: 1px solid var(--border-subtle);
		flex-shrink: 0;
	}
	.h-title {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.h-sub {
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
</style>
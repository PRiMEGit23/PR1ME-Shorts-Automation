<script lang="ts">
	/**
	 * Workbench host — single route (UX §1): per-workbench views. 2S1
	 * renders documented empty states + action affordances for later phases.
	 */
	import EmptyState from '$lib/components/layout/EmptyState.svelte';
	import Button from '$lib/components/primitives/Button.svelte';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import { store } from '../main';
	import { workbenchById } from '$lib/stores/ui.store';

	const wb = $derived(workbenchById(store.ui.workbench));
</script>

<div class="host" class:canvas={wb.id === 'storyboard' || wb.id === 'workflow'}>
	<header class="host-head">
		<span class="h-title label">{wb.label}</span>
		<span class="h-sub mono">{wb.purpose}</span>
	</header>

	{#if wb.id === 'library'}
		<EmptyState
			icon="library"
			title="Welcome to PR1ME Studio"
			subtitle="Create a production to get started — productions own their .env, knowledge base, and run artifacts."
		>
			{#snippet children()}
				<Button variant="cta" icon="plus" title="Production creation arrives with 2S2" disabled>
					New Production
				</Button>
			{/snippet}
		</EmptyState>
	{:else if wb.id === 'script'}
		<EmptyState
			icon="script"
			title="Script"
			subtitle="Pick a topic from the knowledge base (2S3). Press ⌘N to open an empty script document."
		/>
	{:else if wb.id === 'storyboard'}
		<EmptyState
			icon="storyboard"
			title="Storyboard"
			subtitle="Approved candidates will board here after generation (2S4)."
		/>
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
				<Button variant="primary" icon="play" title="Run orchestration arrives with 2S4" disabled>
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
		background-size: 24px 24px;
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
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.h-sub {
		font-size: 10px;
		color: var(--text-tertiary);
	}
</style>
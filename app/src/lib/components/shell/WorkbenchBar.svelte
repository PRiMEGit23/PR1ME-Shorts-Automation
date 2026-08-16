<script lang="ts">
	/**
	 * WorkbenchBar — 44px top bar (VDS §30): 8 workbench tabs (UX §2.1)
	 * with filmstrip perforation underline; Generate CTA + chrome actions.
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import type { IconName } from '$lib/components/primitives/Icon.svelte';
	import { WORKBENCHES, type UiStore } from '$lib/stores/ui.store';
	import type { LayoutStore } from '$lib/stores/layout.store';

	let { ui, layout }: { ui: UiStore; layout: LayoutStore } = $props();
</script>

<nav class="workbenchbar">
	<div class="wb-tabs">
		{#each WORKBENCHES as w (w.id)}
			<button
				class="wb-tab"
				class:active={ui.workbench === w.id}
				title={w.purpose}
				onclick={() => {
					ui.switchWorkbench(w.id);
					layout.setWorkbench(w.id);
				}}
			>
				<span class="wb-tab-icon"><Icon name={w.glyph as IconName} size={17} /></span>
				<span class="wb-tab-label">{w.label}</span>
				{#if ui.workbench === w.id}
					<span class="wb-tab-underline"></span>
				{/if}
			</button>
		{/each}
	</div>
	<div class="wb-actions">
		<Tooltip label="Connections">
			<button class="wb-action" aria-label="Connections" onclick={() => ui.openPalette('commands')}>
				<Icon name="connections" size={15} />
			</button>
		</Tooltip>
		<Tooltip label="Preferences">
			<button class="wb-action" aria-label="Preferences" onclick={() => ui.openPalette('commands')}>
				<Icon name="preferences" size={15} />
			</button>
		</Tooltip>
		<span class="wb-sep"></span>
		<button class="wb-cta" onclick={() => ui.openPalette('commands')}>
			<Icon name="generate" size={15} />
			<span>Generate</span>
		</button>
	</div>
</nav>

<style>
	.workbenchbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: var(--workbenchbar-h);
		padding: 0 var(--space-3);
		background: var(--surface-1);
		border-bottom: 1px solid var(--border-subtle);
		flex-shrink: 0;
		gap: var(--space-4);
	}
	.wb-tabs {
		display: flex;
		align-items: center;
		gap: var(--space-1);
		min-width: 0;
		overflow: hidden;
	}
	.wb-tab {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		height: 34px;
		padding: 0 var(--space-3);
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		font: var(--body-sm-semibold);
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--motion-fast) var(--ease-out),
			color var(--motion-fast) var(--ease-out);
	}
	.wb-tab:hover {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.wb-tab.active {
		color: var(--accent);
	}
	.wb-tab-icon {
		display: inline-flex;
	}
	.wb-tab-label {
		white-space: nowrap;
	}
	.wb-tab-underline {
		position: absolute;
		left: var(--space-3);
		right: var(--space-3);
		bottom: 2px;
		height: 2px;
		border-radius: 1px;
		background: repeating-linear-gradient(90deg, var(--accent) 0 6px, transparent 6px 12px);
	}
	.wb-actions {
		display: flex;
		align-items: center;
		gap: var(--space-1);
		flex-shrink: 0;
	}
	.wb-action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-secondary);
		cursor: pointer;
	}
	.wb-action:hover {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.wb-sep {
		width: 1px;
		height: 18px;
		background: var(--border-default);
		margin: 0 var(--space-1);
	}
	.wb-cta {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		height: 28px;
		padding: 0 var(--space-3);
		border: none;
		border-radius: var(--radius-sm);
		background: var(--cta-bg);
		color: var(--text-primary);
		font: var(--body-sm-semibold);
		box-shadow: var(--shadow-cta);
		cursor: pointer;
	}
	.wb-cta:hover {
		background: var(--cta-bg-hover);
	}
</style>
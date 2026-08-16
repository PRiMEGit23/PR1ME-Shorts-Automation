<script lang="ts">
	/**
	 * WorkbenchBar — 44px top bar (VDS §30): 8 workbench tabs (UX §2.1)
	 * with filmstrip perforation underline; Generate CTA + chrome actions
	 * (VDS §5: ⊕ Generate (primary), ⛁ Connections, ⚙ Preferences).
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import Button from '$lib/components/primitives/Button.svelte';
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
				<span class="wb-tab-icon"><Icon name={w.glyph as IconName} size={24} /></span>
				<span class="wb-tab-label">{w.label}</span>
				{#if ui.workbench === w.id}
					<span class="wb-tab-underline"></span>
				{/if}
			</button>
		{/each}
	</div>
	<div class="wb-actions">
		<Button variant="cta" icon="generate" onclick={() => ui.openPalette('commands')}>Generate</Button>
		<Tooltip label="Connections">
			<IconButton icon="connections" label="Connections" size={28} iconSize={16} onclick={() => ui.openModal('connections')} />
		</Tooltip>
		<Tooltip label="Preferences">
			<IconButton icon="preferences" label="Preferences" size={28} iconSize={16} onclick={() => ui.openPalette('commands')} />
		</Tooltip>
	</div>
</nav>

<style>
	.workbenchbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: var(--chrome-workbench);
		padding: 0 var(--space-3);
		background: var(--surface-0);
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
		font: var(--body-sm);
		font-weight: 600;
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out);
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
</style>
<script lang="ts">
	/**
	 * PanelHeader — 40px panel header (VDS §30). Pin / detach / menu.
	 * Menu: Reset Layout (VDS §39 — documented, working).
	 */
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import type { LayoutStore } from '$lib/stores/layout.store';
	import type { UiStore } from '$lib/stores/ui.store';

	let {
		title,
		panelId,
		layout,
		ui
	}: {
		title: string;
		panelId: string;
		layout: LayoutStore;
		ui: UiStore;
	} = $props();

	let menuOpen = $state(false);

	function pin() {
		const visible = layout.isPanelVisible(panelId as 'explorer' | 'assets' | 'inspector' | 'timeline' | 'terminal');
		layout.pin(panelId as 'explorer' | 'assets' | 'inspector' | 'timeline' | 'terminal', !visible);
	}

	function resetLayout() {
		menuOpen = false;
		layout.resetWorkbench(layout.active);
		ui.pushToast('info', 'Layout reset', {
			message: `${layout.active} restored to its default layout`
		});
	}
</script>

<header class="panel-header">
	<span class="ph-title">{title}</span>
	<span class="ph-actions">
		<IconButton icon="pin" label="Pin / unpin panel" size={26} iconSize={14} onclick={pin} />
		<IconButton icon="detach" label="Detach panel (arrives 2S5)" size={26} iconSize={14} disabled />
		<div class="ph-menu">
			<IconButton icon="menu" label="Panel menu" size={26} iconSize={14} onclick={() => (menuOpen = !menuOpen)} />
			{#if menuOpen}
				<div class="menu-pop" role="menu">
					<button role="menuitem" onclick={resetLayout}>Reset Layout</button>
				</div>
			{/if}
		</div>
	</span>
</header>

<svelte:window onclick={() => (menuOpen = false)} />

<style>
	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: var(--panel-header-h);
		padding: 0 var(--space-2) 0 var(--space-4);
		border-bottom: 1px solid var(--border-subtle);
		flex-shrink: 0;
	}
	.ph-title {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-secondary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.ph-actions {
		display: flex;
		align-items: center;
		gap: 2px;
		opacity: 0;
		transition: opacity var(--dur-fast) var(--ease-out);
	}
	.panel-header:hover .ph-actions {
		opacity: 1;
	}
	.ph-menu {
		position: relative;
	}
	.menu-pop {
		position: absolute;
		top: 30px;
		right: 0;
		z-index: var(--z-popover);
		min-width: 160px;
		padding: var(--space-1);
		border-radius: var(--radius-md);
		border: 1px solid var(--tooltip-border);
		background: var(--tooltip-bg);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		box-shadow: var(--shadow-1);
		animation: pop var(--dur-fast) var(--ease-out) both;
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: scale(0.97) translateY(-2px);
		}
		to {
			opacity: 1;
			transform: scale(1) translateY(0);
		}
	}
	.menu-pop button {
		display: block;
		width: 100%;
		text-align: left;
		padding: var(--space-2) var(--space-3);
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		font: var(--body-sm);
		color: var(--text-primary);
		cursor: pointer;
	}
	.menu-pop button:hover {
		background: var(--surface-3);
	}
</style>
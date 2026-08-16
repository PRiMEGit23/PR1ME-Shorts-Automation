<script lang="ts">
	/**
	 * DockZone — left/right/bottom docks (UX §14): PanelGroup + 4px
	 * DragHandle resize + collapse to 28px edge tab strip (VDS §39).
	 */
	import Panel from './Panel.svelte';
	import PanelGroup from './PanelGroup.svelte';
	import DragHandle from './DragHandle.svelte';
	import EmptyState from './EmptyState.svelte';
	import Icon, { type IconName } from '$lib/components/primitives/Icon.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import { PANEL_IDS, type LayoutStore, type PanelId } from '$lib/stores/layout.store';
	import { PANEL_DEFAULT_ZONE } from '$lib/services/layout.service';
	import type { UiStore } from '$lib/stores/ui.store';

	type Side = 'left' | 'right' | 'bottom';

	let {
		side,
		layout,
		ui
	}: {
		side: Side;
		layout: LayoutStore;
		ui: UiStore;
	} = $props();

	const PANEL_TITLES: Record<PanelId, string> = {
		explorer: 'Explorer',
		assets: 'Assets',
		inspector: 'Inspector',
		timeline: 'Timeline',
		terminal: 'Terminal'
	};

	const zone = $derived(layout.current().zones[side]);
	const size = $derived(layout.current().sizes[side]);
	const collapsed = $derived(layout.current().collapsed[side]);
	/** unpinned panels of this zone auto-hide to the edge strip (VDS §39) */
	const edge = $derived(
		PANEL_IDS.filter(
			(p) => !layout.isPanelPinned(p) && !zone.includes(p) && PANEL_DEFAULT_ZONE[p] === side
		)
	);

	function onDrag(delta: number) {
		// left zone grows when dragging right; right/bottom shrink
		const d = side === 'left' ? delta : -delta;
		layout.setZoneSize(side, layout.current().sizes[side] + d);
	}
</script>

{#snippet body(panel: PanelId)}
	{#if panel === 'explorer'}
		<EmptyState
			icon="explorer"
			title="No productions yet — create one to start."
			subtitle="Productions own their .env, knowledge base, and run artifacts."
		>
			{#snippet children()}
				<button class="ps-btn" title="Production creation arrives with phase 2S2" disabled>
					New Production
				</button>
			{/snippet}
		</EmptyState>
	{:else if panel === 'assets'}
		<EmptyState
			icon="assets"
			title="No media yet"
			subtitle="Render outputs and uploaded assets will land here."
		/>
	{:else if panel === 'inspector'}
		<EmptyState
			icon="inspector"
			title="Nothing selected"
			subtitle="Select an item anywhere to inspect it here."
		/>
	{:else if panel === 'timeline'}
		<EmptyState
			icon="timeline"
			title="No timeline"
			subtitle="Approve candidates in Storyboard to build a timeline."
		/>
	{:else if panel === 'terminal'}
		<EmptyState
			icon="terminal"
			title="Process log"
			subtitle="pr1me output will stream here during runs."
		/>
	{/if}
{/snippet}

{#if collapsed}
	<div class="rail" class:horizontal={side === 'bottom'}>
		{#each [...zone, ...edge] as panel (panel)}
			<Tooltip label={PANEL_TITLES[panel]}>
				<button class="rail-btn" onclick={() => layout.toggleCollapse(side)} aria-label={PANEL_TITLES[panel]}>
					<Icon name={PANEL_GLYPH[panel]} size={15} />
				</button>
			</Tooltip>
		{/each}
	</div>
{:else}
	<div class="dock" class:horizontal={side === 'bottom'} class:right={side === 'right'} style="--zone-size: {size}px">
		{#if side !== 'left'}
			<DragHandle orientation={side === 'bottom' ? 'horizontal' : 'vertical'} ondrag={onDrag} ondblclick={() => layout.toggleCollapse(side)} />
		{/if}
		<div class="fill">
			<PanelGroup direction={side === 'bottom' ? 'horizontal' : 'vertical'}>
				{#each zone as panel (panel)}
					<Panel id={panel} title={PANEL_TITLES[panel]} {layout} {ui}>
						{@render body(panel)}
					</Panel>
				{/each}
			</PanelGroup>
		</div>
		{#if side === 'left'}
			<DragHandle orientation="vertical" ondrag={onDrag} ondblclick={() => layout.toggleCollapse(side)} />
		{/if}
		{#if edge.length > 0}
			<div class="edge-rail" class:horizontal={side === 'bottom'}>
				{#each edge as panel (panel)}
					<Tooltip label={PANEL_TITLES[panel]} below={side === 'bottom'}>
						<button
							class="rail-btn"
							onclick={() => layout.pin(panel, true)}
							aria-label={`Show ${PANEL_TITLES[panel]}`}
						>
							<Icon name={PANEL_GLYPH[panel]} size={15} />
						</button>
					</Tooltip>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.dock {
		display: flex;
		width: var(--zone-size);
		flex-shrink: 0;
		min-width: 0;
		min-height: 0;
		position: relative;
	}
	.dock.horizontal {
		width: auto;
		height: var(--zone-size);
		flex-direction: column;
	}
	.fill {
		flex: 1;
		min-width: 0;
		min-height: 0;
		display: flex;
	}
	.rail {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		width: 28px;
		padding: var(--space-1);
		flex-shrink: 0;
		border-right: 1px solid var(--border-subtle);
	}
	.rail.horizontal {
		flex-direction: row;
		width: auto;
		height: 28px;
		border-right: none;
		border-top: 1px solid var(--border-subtle);
	}
	.edge-rail {
		position: absolute;
		top: 0;
		bottom: 0;
		right: -28px;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		width: 28px;
		padding: var(--space-1);
		background: var(--surface-1);
		border: 1px solid var(--border-subtle);
		border-left: none;
		border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
		z-index: 4;
	}
	.dock.right .edge-rail {
		right: auto;
		left: -28px;
		border-left: 1px solid var(--border-subtle);
		border-right: none;
		border-radius: var(--radius-sm) 0 0 var(--radius-sm);
	}
	.edge-rail.horizontal {
		top: auto;
		right: 0;
		left: 0;
		bottom: -28px;
		flex-direction: row;
		border-left: 1px solid var(--border-subtle);
		border-top: none;
		border-radius: 0 0 var(--radius-sm) var(--radius-sm);
	}
	.rail-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 26px;
		height: 26px;
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-tertiary);
		cursor: pointer;
	}
	.rail-btn:hover {
		background: var(--surface-3);
		color: var(--accent);
	}
	.ps-btn {
		height: var(--control-h);
		padding: 0 var(--space-4);
		border-radius: var(--radius-sm);
		border: none;
		background: var(--btn-primary-bg);
		color: var(--btn-primary-text);
		font: var(--body-sm-semibold);
		cursor: pointer;
	}
	.ps-btn:disabled {
		opacity: 0.45;
		cursor: default;
	}
</style>

<script lang="ts" module>
	const PANEL_GLYPH: Record<PanelId, IconName> = {
		explorer: 'explorer',
		assets: 'assets',
		inspector: 'inspector',
		timeline: 'timeline',
		terminal: 'terminal'
	};
</script>
<script lang="ts">
	/**
	 * ActivityBar — 64px rail (VDS §30): 5 panel toggles (UX §2.2).
	 * Toggle = show in default zone / hide (§39).
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import type { LayoutStore } from '$lib/stores/layout.store';
	import type { UiStore } from '$lib/stores/ui.store';
	import type { IconName } from '$lib/components/primitives/Icon.svelte';

	let { layout, ui }: { layout: LayoutStore; ui: UiStore } = $props();

	const TOGGLES: { id: 'explorer' | 'assets' | 'inspector' | 'timeline' | 'terminal'; label: string; glyph: IconName }[] = [
		{ id: 'explorer', label: 'Explorer', glyph: 'explorer' },
		{ id: 'assets', label: 'Assets', glyph: 'assets' },
		{ id: 'inspector', label: 'Inspector', glyph: 'inspector' },
		{ id: 'timeline', label: 'Timeline', glyph: 'timeline' },
		{ id: 'terminal', label: 'Terminal', glyph: 'terminal' }
	];
</script>

<aside class="activitybar">
	{#each TOGGLES as t (t.id)}
		<Tooltip label={t.label}>
			<button
				class="ab-btn"
				class:active={layout.isPanelVisible(t.id)}
				aria-label={t.label}
				onclick={() => layout.togglePanel(t.id)}
			>
				<Icon name={t.glyph} size={19} />
			</button>
		</Tooltip>
	{/each}
</aside>

<style>
	.activitybar {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-1);
		width: var(--activitybar-w);
		padding: var(--space-2) 0;
		background: var(--surface-0);
		border-right: 1px solid var(--border-subtle);
		flex-shrink: 0;
	}
	.ab-btn {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 40px;
		height: 40px;
		border: none;
		border-radius: var(--radius-md);
		background: transparent;
		color: var(--text-tertiary);
		cursor: pointer;
		transition:
			background-color var(--motion-fast) var(--ease-out),
			color var(--motion-fast) var(--ease-out);
	}
	.ab-btn:hover {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.ab-btn.active {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.ab-btn.active::before {
		content: '';
		position: absolute;
		left: 0;
		top: 50%;
		transform: translateY(-50%);
		width: 2px;
		height: 18px;
		border-radius: 1px;
		background: var(--accent);
	}
</style>
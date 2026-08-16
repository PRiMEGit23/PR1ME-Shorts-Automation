<script lang="ts">
	/**
	 * CommandPalette — global command palette (UX §4): scopes commands /
	 * workbench / jump; fuzzy-ranked groups; 120ms motion (VDS §36).
	 */
	import Icon, { type IconName } from '$lib/components/primitives/Icon.svelte';
	import Kbd from '$lib/components/primitives/Kbd.svelte';
	import SearchField from '$lib/components/data/SearchField.svelte';
	import { fuzzyRank } from '$lib/core/fuzzy';
	import { WORKBENCHES, type PaletteScope, type UiStore } from '$lib/stores/ui.store';
	import type { LayoutStore } from '$lib/stores/layout.store';
	import type { EditorStore } from '$lib/stores/editor.store';
	import type { AppStore } from '$lib/stores/app.store';
	import { di } from '$lib/core/di';

	interface PaletteItem {
		id: string;
		group: string;
		title: string;
		subtitle?: string;
		glyph: IconName;
		kbd?: string;
		run: () => void;
	}

	let {
		ui,
		layout,
		editor,
		app
	}: {
		ui: UiStore;
		layout: LayoutStore;
		editor: EditorStore;
		app: AppStore;
	} = $props();

	let index = $state(0);
	let input = $state('');

	const COMMANDS: PaletteItem[] = [
		{
			id: 'new-script',
			group: 'Commands',
			title: 'New Script document',
			glyph: 'doc',
			kbd: '⌘N',
			run: () => {
				editor.open(editor.newScriptDocument());
				ui.markRecent('new-script');
			}
		},
		{
			id: 'save-layout',
			group: 'Commands',
			title: 'Save layout',
			subtitle: 'Persists the current workbench layout',
			glyph: 'check',
			kbd: '⌘S',
			run: () => {
				void app.saveLayout(di);
				ui.markRecent('save-layout');
			}
		},
		{
			id: 'reset-layout',
			group: 'Commands',
			title: 'Reset Layout',
			subtitle: 'Restore the default dock layout',
			glyph: 'refresh',
			run: () => {
				layout.resetWorkbench(layout.active);
				ui.markRecent('reset-layout');
				ui.pushToast('info', 'Layout reset', { message: 'Restored the default layout.' });
			}
		}
	];

	const WORKBENCH_COMMANDS: PaletteItem[] = WORKBENCHES.map((w, i) => ({
		id: `wb:${w.id}`,
		group: 'Workbenches',
		title: w.label,
		subtitle: w.purpose,
		glyph: w.glyph as IconName,
		kbd: `⌘${i + 1}`,
		run: () => {
			ui.switchWorkbench(w.id);
			layout.setWorkbench(w.id);
			ui.markRecent(`wb:${w.id}`);
		}
	}));

	/** scope jump → empty groups so users can fuzzy-search destinations */
	const GROUPS: { id: PaletteScope; label: string }[] = [
		{ id: 'commands', label: 'Commands' },
		{ id: 'workbench', label: 'Workbenches' },
		{ id: 'jump', label: 'Jump' }
	];

	const allItems = $derived([...COMMANDS, ...WORKBENCH_COMMANDS]);

	const filtered = $derived.by(() => {
		const scope = ui.palette.scope;
		const q = ui.palette.query.trim().toLowerCase();
		let pool: PaletteItem[];
		if (scope === 'workbench' || scope === 'jump') pool = WORKBENCH_COMMANDS;
		else pool = allItems;

		return fuzzyRank(q, pool, (it) => it.title + ' ' + (it.subtitle ?? '')).map((r) => r.item);
	});

	const groups = $derived.by(() => {
		const out: { label: string; items: PaletteItem[] }[] = [];
		for (const it of filtered) {
			let g = out.find((o) => o.label === it.group);
			if (!g) {
				g = { label: it.group, items: [] };
				out.push(g);
			}
			g.items.push(it);
		}
		return out;
	});

	$effect(() => {
		if (ui.palette.open) {
			input = '';
			index = 0;
		}
	});

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			ui.closePalette();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			index = Math.min(filtered.length - 1, index + 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			index = Math.max(0, index - 1);
		} else if (e.key === 'Tab') {
			e.preventDefault();
			// jump to the first item of the next group (wrapping)
			const current = filtered[index]?.group;
			let start = -1;
			for (let i = index + 1; i < filtered.length; i++) {
				if (filtered[i]!.group !== current) {
					start = i;
					break;
				}
			}
			if (start < 0) {
				for (let i = 0; i < index; i++) {
					if (filtered[i]!.group !== current) {
						start = i;
						break;
					}
				}
			}
			if (start >= 0) index = start;
		} else if (e.key === 'Enter') {
			e.preventDefault();
			const it = filtered[index];
			if (it) {
				it.run();
				ui.closePalette();
			}
		}
	}

	function pick(it: PaletteItem) {
		it.run();
		ui.closePalette();
	}
</script>

{#if ui.palette.open}
	<div
		class="backdrop"
		role="presentation"
		onclick={() => ui.closePalette()}
		onkeydown={(e) => e.key === 'Escape' && ui.closePalette()}
	>
		<div
			class="palette"
			role="dialog"
			aria-label="Command palette"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.key === 'Escape' && ui.closePalette()}
		>
			<div class="pal-head">
				<div class="pal-scopes">
					{#each GROUPS as g (g.id)}
						<button
							class="scope"
							class:active={ui.palette.scope === g.id}
							onclick={() => ui.openPalette(g.id)}
						>
							{g.label}
						</button>
					{/each}
				</div>
				<SearchField bind:value={input} placeholder="Type a command or search…" onkeydown={onKeydown} autofocus />
			</div>
			<div class="pal-results">
				{#each groups as group (group.label)}
					<div class="g">
						<div class="g-label">{group.label}</div>
						{#each group.items as it, i (it.id)}
							<button
								class="row"
								class:active={filtered.indexOf(it) === index}
								onclick={() => pick(it)}
								onmouseenter={() => (index = filtered.indexOf(it))}
							>
								<span class="row-icon"><Icon name={it.glyph} size={16} /></span>
								<span class="row-body">
									<span class="row-title">{it.title}</span>
									{#if it.subtitle}
										<span class="row-sub">{it.subtitle}</span>
									{/if}
								</span>
								{#if it.kbd}
									<Kbd>{it.kbd}</Kbd>
								{/if}
							</button>
						{/each}
					</div>
				{/each}
				{#if filtered.length === 0}
					<div class="empty-row">No matches for “{ui.palette.query}”</div>
				{/if}
			</div>
			<div class="pal-foot">
				<span class="mono">↑↓ navigate · tab group · ↵ run</span>
				<span class="mono">esc dismiss</span>
			</div>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: var(--z-palette);
		background: var(--overlay);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding-top: 12vh;
	}
	.palette {
		width: min(600px, 90vw);
		border-radius: var(--radius-lg);
		border: 1px solid var(--border-default);
		background: var(--surface-glass);
		backdrop-filter: blur(12px) saturate(1.4);
		-webkit-backdrop-filter: blur(12px) saturate(1.4);
		box-shadow: var(--shadow-3);
		overflow: hidden;
		animation: open 120ms var(--ease-out) both;
	}
	@keyframes open {
		from {
			opacity: 0;
			transform: scale(0.98) translateY(-4px);
		}
		to {
			opacity: 1;
			transform: scale(1) translateY(0);
		}
	}
	.pal-head {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		padding: var(--space-4);
		border-bottom: 1px solid var(--border-subtle);
	}
	.pal-scopes {
		display: flex;
		gap: var(--space-1);
	}
	.scope {
		height: 26px;
		padding: 0 var(--space-3);
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-tertiary);
		cursor: pointer;
	}
	.scope:hover {
		color: var(--text-secondary);
	}
	.scope.active {
		background: var(--surface-3);
		color: var(--text-primary);
	}
	.pal-results {
		max-height: 46vh;
		overflow: auto;
		padding: var(--space-2);
	}
	.g {
		margin-bottom: var(--space-1);
	}
	.g-label {
		padding: var(--space-2) var(--space-3) var(--space-1);
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-tertiary);
	}
	.row {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		width: 100%;
		padding: var(--space-2) var(--space-3);
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		text-align: left;
		cursor: pointer;
	}
	.row.active {
		background: var(--accent-soft);
	}
	.row-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		flex-shrink: 0;
		border-radius: var(--radius-sm);
		background: var(--surface-3);
		color: var(--text-secondary);
	}
	.row.active .row-icon {
		background: var(--accent);
		color: var(--text-primary);
	}
	.row-body {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 1px;
	}
	.row-title {
		font: var(--body-sm);
		font-weight: 600;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.row-sub {
		font: var(--body-sm);
		color: var(--text-secondary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.empty-row {
		padding: var(--space-6) var(--space-3);
		text-align: center;
		font: var(--body-sm);
		color: var(--text-tertiary);
	}
	.pal-foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: var(--space-2) var(--space-4);
		border-top: 1px solid var(--border-subtle);
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
	.mono {
		font-family: var(--font-mono);
	}
</style>
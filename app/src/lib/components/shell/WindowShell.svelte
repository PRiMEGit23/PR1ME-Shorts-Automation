<script lang="ts">
	/**
	 * WindowShell — application frame: title bar, workbench bar, activity
	 * bar, docks, editor area, status bar + overlays (startup screen,
	 * command palette, toasts). Global shortcuts (UX §5 / VDS §8).
	 */
	import TitleBar from './TitleBar.svelte';
	import WorkbenchBar from './WorkbenchBar.svelte';
	import ActivityBar from './ActivityBar.svelte';
	import DockZone from '$lib/components/layout/DockZone.svelte';
	import EditorArea from './EditorArea.svelte';
	import StatusBar from './StatusBar.svelte';
	import CommandPalette from './CommandPalette.svelte';
	import Toast from '$lib/components/primitives/Toast.svelte';
	import { WORKBENCHES, type UiStore } from '$lib/stores/ui.store';
	import type { LayoutStore } from '$lib/stores/layout.store';
	import type { EditorStore } from '$lib/stores/editor.store';
	import type { AppStore } from '$lib/stores/app.store';
	import { di } from '$lib/core/di';
	import type { Snippet } from 'svelte';

	let {
		ui,
		layout,
		editor,
		app,
		children
	}: {
		ui: UiStore;
		layout: LayoutStore;
		editor: EditorStore;
		app: AppStore;
		children?: Snippet;
	} = $props();

	function isMod(e: KeyboardEvent) {
		return e.metaKey || e.ctrlKey;
	}

	function onKeydown(e: KeyboardEvent) {
		// palette: Cmd/Ctrl+K, Ctrl+P, Ctrl+Shift+P
		if (isMod(e) && (e.key === 'k' || e.key === 'K')) {
			e.preventDefault();
			ui.palette.open ? ui.closePalette() : ui.openPalette('commands');
			return;
		}
		if ((e.ctrlKey && e.key === 'p') || (e.ctrlKey && e.shiftKey && e.key === 'P')) {
			e.preventDefault();
			ui.openPalette(e.ctrlKey && e.shiftKey ? 'workbench' : 'commands');
			return;
		}
		// workbench switching Cmd/Ctrl+1..8
		if (isMod(e) && !e.shiftKey && e.key >= '1' && e.key <= '8') {
			e.preventDefault();
			const wb = WORKBENCHES[Number(e.key) - 1];
			if (wb) {
				ui.switchWorkbench(wb.id);
				layout.setWorkbench(wb.id);
			}
			return;
		}
		// Cmd/Ctrl+B — toggle left dock
		if (isMod(e) && e.key === 'b') {
			e.preventDefault();
			layout.toggleCollapse('left');
			return;
		}
		// Cmd/Ctrl+Shift+E/A/I/T/` — panel toggles
		if (isMod(e) && e.shiftKey) {
			const map: Record<string, 'explorer' | 'assets' | 'inspector' | 'timeline' | 'terminal'> = {
				e: 'explorer',
				a: 'assets',
				i: 'inspector',
				t: 'timeline',
				'`': 'terminal'
			};
			const panel = map[e.key];
			if (panel) {
				e.preventDefault();
				layout.togglePanel(panel);
				return;
			}
		}
		// tabs
		if (e.ctrlKey && e.key === 'Tab') return; // handled by EditorTabs
		if (isMod(e) && e.key === 'w') {
			e.preventDefault();
			if (editor.activeId) editor.close(editor.activeId);
			return;
		}
		if (isMod(e) && e.shiftKey && e.key === 't') {
			e.preventDefault();
			editor.reopenLastClosed();
			return;
		}
		// undo/redo
		if (isMod(e) && e.key === 'z') {
			if (editor.activeId) {
				e.preventDefault();
				e.shiftKey ? editor.redoDocument(editor.activeId) : editor.undoDocument(editor.activeId);
			}
			return;
		}
		// save: document (or layout when no document)
		if (isMod(e) && e.key === 's') {
			e.preventDefault();
			if (editor.active()) {
				editor.markDirty(editor.activeId!, false);
				ui.pushToast('success', 'Document saved', {
					message: 'Document state is in-memory in 2S1.'
				});
			} else {
				void app.saveLayout(di);
			}
			return;
		}
		// Escape — dismiss palette
		if (e.key === 'Escape' && ui.palette.open) {
			ui.closePalette();
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div class="shell">
	{#if !ui.booted}
		<!-- startup screen (M1) -->
		<div class="startup">
			<div class="su-mark">
				<span class="su-aperture"></span>
				<span class="su-wordmark">
					<span class="su-p">PR1ME</span>
					<span class="su-studio">STUDIO</span>
				</span>
			</div>
			<div class="su-tagline">Make the Short.</div>
			<div class="su-progress mono">
				<span class="su-fill" style="width: {app.bootPhase ? 50 : 100}%"></span>
			</div>
			<div class="su-phase mono">{app.bootPhase || 'ready'}</div>
			<div class="su-foot mono">
				<span>v0.2.1</span>
				<span>·</span>
				<span>pr1me {app.version?.version ?? '—'}</span>
			</div>
		</div>
	{:else}
		<TitleBar {ui} />
		<WorkbenchBar {ui} {layout} />
		<div class="stage">
			<ActivityBar {layout} {ui} />
			<div class="main">
				<div class="row">
					<DockZone side="left" {layout} {ui} />
					<EditorArea {editor} {ui}>
						{@render children?.()}
					</EditorArea>
					<DockZone side="right" {layout} {ui} />
				</div>
				<DockZone side="bottom" {layout} {ui} />
			</div>
		</div>
		<StatusBar {app} />
	{/if}

	{#if ui.palette.open}
		<CommandPalette {ui} {layout} {editor} {app} />
	{/if}

	<div class="toasts">
		{#each ui.toasts as t (t.id)}
			<Toast item={t} ondismiss={() => ui.dismissToast(t.id)} />
		{/each}
	</div>
</div>

<style>
	.shell {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
		background: var(--surface-0);
	}
	.stage {
		display: flex;
		flex: 1;
		min-width: 0;
		min-height: 0;
		overflow: hidden;
		position: relative;
	}
	.main {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
		min-height: 0;
	}
	.row {
		display: flex;
		flex: 1;
		min-width: 0;
		min-height: 0;
	}
	.toasts {
		position: fixed;
		right: var(--space-5);
		bottom: calc(var(--statusbar-h) + var(--space-5));
		z-index: var(--z-toast);
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: var(--space-2);
	}
	.startup {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-4);
		background: var(--surface-0);
		animation: fade var(--motion-normal) var(--ease-out) both;
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
	.su-mark {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-3);
	}
	.su-aperture {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		border: 2px solid var(--accent);
		position: relative;
		box-shadow: var(--glow-accent);
	}
	.su-aperture::before,
	.su-aperture::after {
		content: '';
		position: absolute;
		top: 50%;
		left: 50%;
		width: 72px;
		height: 2px;
		background: var(--accent);
		transform-origin: center;
	}
	.su-aperture::before {
		transform: translate(-50%, -50%) rotate(30deg);
	}
	.su-aperture::after {
		transform: translate(-50%, -50%) rotate(-30deg);
	}
	.su-wordmark {
		display: flex;
		align-items: baseline;
		gap: var(--space-3);
	}
	.su-p {
		font: var(--display-2xl);
		letter-spacing: 0.24em;
		color: var(--text-primary);
	}
	.su-studio {
		font: var(--mono-sm);
		letter-spacing: 0.4em;
		color: var(--text-tertiary);
	}
	.su-tagline {
		font: var(--body-sm);
		color: var(--text-secondary);
	}
	.su-progress {
		width: 260px;
		height: 4px;
		border-radius: 2px;
		background: var(--surface-3);
		overflow: hidden;
		margin-top: var(--space-3);
	}
	.su-fill {
		display: block;
		height: 100%;
		border-radius: 2px;
		background: var(--accent);
		transition: width var(--motion-normal) var(--ease-out);
	}
	.su-phase {
		font-size: 10px;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		color: var(--text-tertiary);
	}
	.su-foot {
		position: absolute;
		bottom: var(--space-5);
		display: flex;
		gap: var(--space-3);
		font-size: 10px;
		color: var(--text-tertiary);
	}
</style>
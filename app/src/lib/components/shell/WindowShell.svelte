<script lang="ts">
	/**
	 * WindowShell — application frame: title bar, workbench bar, activity
	 * bar, docks, editor area, status bar + overlays (startup screen,
	 * command palette, toasts). Global shortcuts (UX §5 / VDS §8).
	 */
	import TitleBar from './TitleBar.svelte';
	import WorkbenchBar from './WorkbenchBar.svelte';
	import ActivityBar from './ActivityBar.svelte';
	import DockZone from '$lib/components/shell/DockZone.svelte';
	import EditorArea from './EditorArea.svelte';
	import StatusBar from './StatusBar.svelte';
	import CommandPalette from './CommandPalette.svelte';
	import ConnectionCenter from './ConnectionCenter.svelte';
	import ConfirmDialog from './ConfirmDialog.svelte';
	import Toast from '$lib/components/primitives/Toast.svelte';
	import ApertureMark from '$lib/components/primitives/ApertureMark.svelte';
	import { WORKBENCHES, type UiStore } from '$lib/stores/ui.store';
	import type { LayoutStore } from '$lib/stores/layout.store';
	import type { EditorStore } from '$lib/stores/editor.store';
	import type { AppStore } from '$lib/stores/app.store';
	import type { ProvidersStore } from '$lib/stores/providers.store';
	import type { KnowledgeStore } from '$lib/stores/knowledge.store';
	import type { ConnectionsVm } from '$lib/viewmodels/connections.vm';
	import type { ScriptVm } from '$lib/viewmodels/script.vm';
	import { di } from '$lib/core/di';
	import { APP_VERSION } from '$lib/core/config';
	import type { Snippet } from 'svelte';

	let {
		ui,
		layout,
		editor,
		app,
		providers,
		connections,
		knowledge,
		script,
		children
	}: {
		ui: UiStore;
		layout: LayoutStore;
		editor: EditorStore;
		app: AppStore;
		providers: ProvidersStore;
		connections: ConnectionsVm | null;
		knowledge: KnowledgeStore;
		script: ScriptVm | null;
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
		// Script workbench (2S3): Cmd/Ctrl+S save KB, Cmd/Ctrl+E open editor,
		// Cmd/Ctrl+D duplicate row, Cmd/Ctrl+F focus search
		if (isMod(e) && !e.shiftKey && e.key === 's' && ui.workbench === 'script' && script) {
			e.preventDefault();
			if (knowledge.editor.open) {
				void script.commitAndSave();
			} else {
				void script.save();
			}
			return;
		}
		if (isMod(e) && e.key === 'e' && ui.workbench === 'script' && script) {
			e.preventDefault();
			const index = knowledge.selected ?? 0;
			if (index >= 0 && index < knowledge.allRows.length) knowledge.openEditor(index);
			return;
		}
		if (isMod(e) && e.key === 'd' && ui.workbench === 'script' && knowledge.editor.open) {
			e.preventDefault();
			const index = knowledge.editor.rowIndex ?? 0;
			if (index < knowledge.allRows.length) knowledge.duplicateRow(index);
			return;
		}
		if (isMod(e) && e.key === 'f' && ui.workbench === 'script') {
			e.preventDefault();
			document.getElementById('kb-search')?.focus();
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
		// Escape — dismiss palette, confirm dialog or modal (UX §15)
		if (e.key === 'Escape') {
			if (ui.palette.open) {
				ui.closePalette();
			} else if (ui.confirm) {
				ui.resolveConfirm(false);
			} else if (ui.modal !== 'none') {
				ui.closeModal();
			}
		}
		// Connection Center: Cmd/Ctrl+Shift+D (UX §15)
		if (isMod(e) && e.shiftKey && (e.key === 'd' || e.key === 'D')) {
			e.preventDefault();
			ui.modal === 'connections' ? ui.closeModal() : ui.openModal('connections');
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div class="shell">
	{#if !ui.booted}
		<!-- startup screen (M1) -->
		<div class="startup">
			<div class="su-mark">
				<ApertureMark size={48} />
				<div class="su-wordmark">PR1ME</div>
				<div class="su-studio">STUDIO</div>
			</div>
			<div class="su-tagline">Make the Short.</div>
			<div class="su-progress mono" role="status">
				<span class="su-blocks">████████████░░░░░░░░</span>
				<span class="su-pct">50%</span>
				<span class="su-label">loading services</span>
			</div>
			<div class="su-foot mono">
				<span>v{APP_VERSION} · pr1me {app.version?.version ?? '—'}</span>
				<span class="su-copy">© PR1M3 Labs</span>
			</div>
		</div>
	{:else}
		<TitleBar {ui} {providers} />
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
		<StatusBar {app} {providers} {ui} />
	{/if}

	{#if ui.palette.open}
		<CommandPalette {ui} {layout} {editor} {app} />
	{/if}

	{#if ui.modal === 'connections' && connections}
		<ConnectionCenter ui={ui} store={providers} vm={connections} />
	{/if}

	{#if ui.confirm}
		<ConfirmDialog confirm={ui.confirm} onResolve={(ok) => ui.resolveConfirm(ok)} />
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
		bottom: calc(var(--chrome-status) + var(--space-5));
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
		box-shadow: inset 0 0 0 1px transparent;
		animation: fade var(--dur-slow) var(--ease-out) both;
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
	.su-wordmark {
		font: var(--display-2xl);
		letter-spacing: 0.24em;
		text-indent: 0.24em;
		background: var(--accent-gradient);
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
	}
	.su-studio {
		font: var(--label);
		text-transform: uppercase;
		letter-spacing: 0.3em;
		text-indent: 0.3em;
		color: var(--text-tertiary);
	}
	.su-tagline {
		font: var(--body-sm);
		color: var(--text-secondary);
	}
	.su-progress {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		margin-top: var(--space-3);
		font: var(--mono-sm);
		color: var(--text-secondary);
	}
	.su-blocks {
		color: var(--accent);
	}
	.su-pct {
		color: var(--text-primary);
	}
	.su-label {
		text-transform: uppercase;
		font: var(--label);
		color: var(--text-tertiary);
	}
	.su-foot {
		position: absolute;
		left: var(--space-5);
		right: var(--space-5);
		bottom: var(--space-5);
		display: flex;
		align-items: center;
		justify-content: space-between;
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
	.su-copy {
		color: var(--text-tertiary);
	}
</style>
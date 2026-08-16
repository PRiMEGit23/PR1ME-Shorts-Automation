/**
 * UI store — active workbench, palette, toasts, modals, theme, shortcuts help.
 * Slice of the AppStore (PRODUCT_LAYER §5).
 */

export type WorkbenchId =
	| 'library'
	| 'script'
	| 'storyboard'
	| 'workflow'
	| 'render'
	| 'edit'
	| 'deliver'
	| 'insights';

export type PaletteScope = 'commands' | 'workbench' | 'jump';

export interface PaletteState {
	open: boolean;
	scope: PaletteScope;
	query: string;
}

export type ToastKind = 'success' | 'error' | 'info' | 'progress';

export interface ToastItem {
	id: string;
	kind: ToastKind;
	title: string;
	message?: string;
	action?: { label: string; run: () => void };
	/** auto-dismiss ms; 0 = persists until dismissed (errors) */
	ttl: number;
}

export type ModalKind = 'none' | 'preferences' | 'connections' | 'confirm';

/** Workbench registry (UX_ARCHITECTURE §2.1 — the ONLY top-level destinations). */
export interface WorkbenchDef {
	id: WorkbenchId;
	label: string;
	glyph: string;
	purpose: string;
}

export const WORKBENCHES: WorkbenchDef[] = [
	{ id: 'library', label: 'Library', glyph: 'library', purpose: 'Productions, recent episodes, welcome' },
	{ id: 'script', label: 'Script', glyph: 'script', purpose: 'Knowledge base, topic selection, script editing' },
	{ id: 'storyboard', label: 'Storyboard', glyph: 'storyboard', purpose: 'Scene board: candidates, approve, camera plan' },
	{ id: 'workflow', label: 'Workflow', glyph: 'workflow', purpose: 'Prompt chain + ComfyUI graph' },
	{ id: 'render', label: 'Render', glyph: 'render', purpose: 'Render board: queue, live stages' },
	{ id: 'edit', label: 'Edit', glyph: 'edit', purpose: 'Timeline + player' },
	{ id: 'deliver', label: 'Deliver', glyph: 'deliver', purpose: 'Publish targets, metadata review' },
	{ id: 'insights', label: 'Insights', glyph: 'insights', purpose: 'Analytics + learning proposals' }
];

export function workbenchById(id: WorkbenchId): WorkbenchDef {
	return WORKBENCHES.find((w) => w.id === id) ?? WORKBENCHES[0]!;
}

const DEFAULT_PALETTE: PaletteState = { open: false, scope: 'commands', query: '' };

export class UiStore {
	workbench: WorkbenchId = $state('library');
	palette: PaletteState = $state({ ...DEFAULT_PALETTE });
	toasts: ToastItem[] = $state([]);
	modal: ModalKind = $state('none');
	theme: 'dark' = $state('dark');
	booted: boolean = $state(false);
	shortcutsHelpOpen: boolean = $state(false);

	/** Palette recents (in-memory; persisted per-production in 2S2). */
	recents: string[] = $state([]);

	constructor(private readonly toastFactory: (item: Omit<ToastItem, 'id'>) => string = defaultToastId) {}

	switchWorkbench(id: WorkbenchId): void {
		this.workbench = id;
		this.closePalette();
	}

	openPalette(scope: PaletteScope): void {
		this.palette = { open: true, scope, query: '' };
	}

	closePalette(): void {
		this.palette = { ...this.palette, open: false };
	}

	setPaletteQuery(query: string): void {
		this.palette = { ...this.palette, query };
	}

	markRecent(id: string): void {
		this.recents = [id, ...this.recents.filter((r) => r !== id)].slice(0, 12);
	}

	pushToast(
		kind: ToastKind,
		title: string,
		opts: { message?: string; action?: { label: string; run: () => void }; ttl?: number } = {}
	): ToastItem {
		const base: Omit<ToastItem, 'id'> = {
			kind,
			title,
			message: opts.message,
			action: opts.action,
			ttl: opts.ttl ?? (kind === 'error' ? 0 : 4000)
		};
		const item: ToastItem = { ...base, id: this.toastFactory(base) };
		// max 4 toasts; newest at the bottom of the stack
		this.toasts = [...this.toasts.slice(-3), item];
		return item;
	}

	dismissToast(id: string): void {
		this.toasts = this.toasts.filter((t) => t.id !== id);
	}

	openModal(kind: Exclude<ModalKind, 'none'>): void {
		// palette closes when a dialog opens (VDS §20)
		this.palette = { ...this.palette, open: false };
		this.modal = kind;
	}

	closeModal(): void {
		this.modal = 'none';
	}

	toggleShortcutsHelp(): void {
		this.shortcutsHelpOpen = !this.shortcutsHelpOpen;
	}

	setBooted(): void {
		this.booted = true;
	}
}

function defaultToastId(item: Omit<ToastItem, 'id'>): string {
	return `${item.kind}-${crypto.randomUUID()}`;
}
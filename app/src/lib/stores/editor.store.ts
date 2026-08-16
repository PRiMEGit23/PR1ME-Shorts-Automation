/**
 * Editor store — open documents, tabs, dirty state, undo/redo scaffolding.
 * First document type: empty ScriptDocument shell (IMPLEMENTATION_PLAN 2S1 §10).
 */

export type DocumentType = 'script' | 'storyboard' | 'workflow' | 'deliver';

export interface EditorDocument {
	id: string;
	type: DocumentType;
	title: string;
	dirty: boolean;
}

export interface ScriptDocument extends EditorDocument {
	type: 'script';
	topic: string;
	narration: string;
	category: string;
	difficulty: 'B' | 'I' | 'A';
}

interface UndoEntry {
	before: string;
	after?: string;
}

export class EditorStore {
	documents: EditorDocument[] = $state([]);
	activeId: string | null = $state(null);
	closed: EditorDocument[] = $state([]);
	/** per-document undo stacks (JSON snapshots) */
	undo: Record<string, UndoEntry[]> = $state({});
	redo: Record<string, UndoEntry[]> = $state({});

	open(document: EditorDocument): void {
		if (!this.documents.some((d) => d.id === document.id)) {
			this.documents = [...this.documents, document];
		}
		this.activeId = document.id;
	}

	activate(id: string): void {
		this.activeId = id;
	}

	active(): EditorDocument | null {
		return this.documents.find((d) => d.id === this.activeId) ?? null;
	}

	close(id: string): void {
		const doc = this.documents.find((d) => d.id === id);
		if (!doc) return;
		this.closed = [...this.closed, doc];
		this.documents = this.documents.filter((d) => d.id !== id);
		if (this.activeId === id) {
			this.activeId = this.documents.at(-1)?.id ?? null;
		}
	}

	/** Cmd+Shift+T — reopen the last closed document. */
	reopenLastClosed(): void {
		const doc = this.closed.at(-1);
		if (!doc) return;
		this.closed = this.closed.slice(0, -1);
		this.open({ ...doc, dirty: false });
	}

	markDirty(id: string, dirty: boolean): void {
		this.documents = this.documents.map((d) => (d.id === id ? { ...d, dirty } : d));
	}

	/** Apply a patch to a document (snapshots before the first edit). */
	updateDocument<T extends EditorDocument>(id: string, patch: Partial<T>): void {
		const doc = this.documents.find((d) => d.id === id) as T | undefined;
		if (!doc) return;
		if (!doc.dirty) {
			this.undo[id] = [...(this.undo[id] ?? []), { before: JSON.stringify(doc) }].slice(-100);
			this.redo[id] = [];
		}
		const next = { ...doc, ...patch, dirty: true };
		this.documents = this.documents.map((d) => (d.id === id ? next : d));
		const top = this.undo[id]?.at(-1);
		if (top) top.after = JSON.stringify(next);
	}

	/** Undo/redo scaffolding: snapshot the document before a mutation. */
	snapshot(id: string): void {
		const doc = this.documents.find((d) => d.id === id);
		if (!doc) return;
		this.undo[id] = [...(this.undo[id] ?? []), { before: JSON.stringify(doc) }].slice(-100);
		this.redo[id] = [];
	}

	undoDocument(id: string): boolean {
		const stack = this.undo[id];
		const entry = stack?.at(-1);
		if (!stack || !entry) return false;
		this.undo[id] = stack.slice(0, -1);
		this.redo[id] = [...(this.redo[id] ?? []), entry];
		const restored = JSON.parse(entry.before) as EditorDocument;
		this.documents = this.documents.map((d) => (d.id === id ? restored : d));
		return true;
	}

	redoDocument(id: string): boolean {
		const stack = this.redo[id];
		const entry = stack?.at(-1);
		if (!stack || !entry || entry.after === undefined) return false;
		this.redo[id] = stack.slice(0, -1);
		this.undo[id] = [...(this.undo[id] ?? []), entry];
		const restored = JSON.parse(entry.after) as EditorDocument;
		this.documents = this.documents.map((d) => (d.id === id ? restored : d));
		return true;
	}

	/** New empty Script document (2S1 §10). */
	newScriptDocument(): ScriptDocument {
		return {
			id: crypto.randomUUID(),
			type: 'script',
			title: 'Untitled script',
			dirty: false,
			topic: '',
			narration: '',
			category: '',
			difficulty: 'B'
		};
	}
}
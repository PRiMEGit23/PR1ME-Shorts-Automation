/**
 * Script VM — Script Workbench orchestration (IMPLEMENTATION_PLAN 2S3,
 * PRODUCT_LAYER §4): browse/validate/edit the knowledge base. Services
 * call the bridge; the store applies results; the VM owns async flows
 * (reload, debounced search, validate-all, save, import, export).
 */

import type { AppServices } from '$lib/core/di';
import type { UiStore } from '$lib/stores/ui.store';
import type { KnowledgeStore } from '$lib/stores/knowledge.store';
import type { KnowledgeRow, KnowledgeSource } from '$lib/models/knowledge';

const KB_CSV = 'knowledge_base.csv';
const TOPICS_CSV = 'topics.csv';
/** Whole-file window: backend caps pages at 10k, KB is ~400 rows now. */
const FULL_LOAD = 10_000;
const SEARCH_DEBOUNCE_MS = 350;

export class ScriptVm {
	private searchTimer: ReturnType<typeof setTimeout> | null = null;
	private generation = 0;

	constructor(
		private readonly ui: UiStore,
		readonly store: KnowledgeStore,
		private readonly services: AppServices
	) {}

	relPath(): string {
		return this.store.source === 'knowledge' ? KB_CSV : TOPICS_CSV;
	}

	/** Initial load for a workbench open — reads the current source. */
	async open(): Promise<void> {
		await this.reload();
	}

	async reload(): Promise<void> {
		const gen = ++this.generation;
		this.store.loading = true;
		try {
			const page = await this.services.knowledge.load(this.relPath(), 0, FULL_LOAD);
			if (gen !== this.generation) return;
			this.store.applyPage(rowsFromPage(page), page.total);
		} catch (err) {
			if (gen !== this.generation) return;
			this.store.loading = false;
			this.ui.pushToast('error', `${this.store.source} not loaded`, {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}

	async setSource(source: KnowledgeSource): Promise<void> {
		this.store.setSource(source);
		this.store.clearValidation();
		await this.reload();
	}

	/** Debounced backend search over the whole table. */
	onSearch(query: string): void {
		this.store.setQuery(query);
		if (this.searchTimer) clearTimeout(this.searchTimer);
		this.searchTimer = setTimeout(() => void this.runSearch(query), SEARCH_DEBOUNCE_MS);
	}

	private async runSearch(query: string): Promise<void> {
		if (query !== this.store.query) return;
		const gen = ++this.generation;
		this.store.searching = true;
		try {
			const page = await this.services.knowledge.search(this.relPath(), query, 0, FULL_LOAD);
			if (gen !== this.generation) return;
			this.store.applyPage(rowsFromPage(page), page.total);
			this.store.clearValidation();
		} catch (err) {
			if (gen !== this.generation) return;
			this.store.searching = false;
			this.ui.pushToast('error', 'Search failed', {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}

	/** Validate-all: spinner toast → report → inline issues + summary. */
	async validateAll(): Promise<void> {
		const toast = this.ui.pushToast('progress', 'Validating knowledge base', {
			message: 'Running validate_knowledge_csv.py…',
			ttl: 0
		});
		try {
			const report = await this.services.knowledge.validate(this.relPath());
			this.ui.dismissToast(toast.id);
			this.store.applyValidation(report);
			this.ui.pushToast(report.valid ? 'success' : 'error', report.valid ? 'Knowledge base is valid' : `${report.errors.length} error(s) found`, {
				message: report.valid ? `Last checked ${new Date(report.checkedAt).toLocaleTimeString()}` : 'Fix rows or override before saving',
				ttl: report.valid ? 4000 : 8000
			});
		} catch (err) {
			this.ui.dismissToast(toast.id);
			this.ui.pushToast('error', 'Validation failed', {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}

	/** Save the table (blocked on validation errors unless overridden). */
	async save(): Promise<boolean> {
		if (!this.store.tableDirty) {
			this.ui.pushToast('info', 'No changes to save');
			return false;
		}
		if (!this.store.allowSaveWithErrors && this.hasErrors()) {
			this.ui.pushToast('error', 'Cannot save — validation errors', {
				message: `${this.errorCount()} error(s). Fix them or enable "save with errors".`
			});
			return false;
		}
		try {
			await this.services.knowledge.save(this.relPath(), this.store.allRows);
			this.store.markSaved();
			this.ui.pushToast('success', `${this.store.source === 'knowledge' ? 'Knowledge base' : 'Topics'} saved`, {
				message: `${this.store.total} rows · atomic write`
			});
			return true;
		} catch (err) {
			this.ui.pushToast('error', 'Save failed', {
				message: err instanceof Error ? err.message : String(err)
			});
			return false;
		}
	}

	/** Import flow: pick → preview → confirm → apply to the table. */
	async import(): Promise<void> {
		const picked = await this.services.knowledge.pickImportPath();
		if (!picked) return;
		let page;
		try {
			page = await this.services.knowledge.importPreview(picked);
		} catch (err) {
			this.ui.pushToast('error', 'Import failed', {
				message: err instanceof Error ? err.message : String(err)
			});
			return;
		}
		if (page.header.length !== this.store.header.length) {
			this.ui.pushToast('error', 'Import rejected', {
				message: `Expected ${this.store.header.length} columns, got ${page.header.length}.`
			});
			return;
		}
		const ok = await this.ui.askConfirm({
			title: `Replace ${this.store.source} table?`,
			message: `${page.total} row(s) from ${picked}. The current table is replaced once you save.`,
			confirmLabel: 'Import',
			danger: true
		});
		if (!ok) return;
		this.store.applyPage(rowsFromPage(page), page.total);
		this.store.tableDirty = true;
		this.store.clearValidation();
		this.ui.pushToast('success', 'Imported into the editor', {
			message: 'Press save to write the table'
		});
	}

	/** Export flow: pick destination → atomic write of the full table. */
	async export(): Promise<void> {
		const picked = await this.services.knowledge.pickExportPath();
		if (!picked) return;
		try {
			await this.services.knowledge.exportTo(picked, this.store.allRows);
			this.ui.pushToast('success', 'Exported', {
				message: `${this.store.total} rows written`
			});
		} catch (err) {
			this.ui.pushToast('error', 'Export failed', {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}

	/** Bring a row into the visible window (jump-to-row from validation). */
	jumpToRow(fileRow: number): void {
		const index = fileRow - 1;
		if (index < 0) return;
		const sliceStart = Math.floor(index / this.store.windowSize) * this.store.windowSize;
		this.store.windowOffset = sliceStart;
	}

	errorCount(): number {
		return this.store.validation?.errors.length ?? 0;
	}

	hasErrors(): boolean {
		return this.errorCount() > 0;
	}

	/** Editor: commit → save. Row edit/add/duplicate/delete live on the store. */
	async commitAndSave(): Promise<boolean> {
		this.store.commitDraft();
		return this.save();
	}

	/** Delete with confirmation (VDS confirm dialog). */
	async requestDelete(rowIndex: number): Promise<void> {
		const row = this.store.allRows[rowIndex];
		const topic = row?.topic || `row ${rowIndex + 1}`;
		const ok = await this.ui.askConfirm({
			title: `Delete "${topic}"?`,
			message: 'The row is removed from the table until you save.',
			confirmLabel: 'Delete',
			danger: true
		});
		if (!ok) return;
		this.store.deleteRow(rowIndex);
	}
}

/** rows: string[][] → KnowledgeRow[] (header-driven). */
function rowsFromPage(page: { header: string[]; rows: string[][]; total: number }): KnowledgeRow[] {
	return page.rows.map((cells) => {
		const row: KnowledgeRow = {};
		for (let i = 0; i < page.header.length; i++) row[page.header[i]!] = cells[i] ?? '';
		return row;
	});
}

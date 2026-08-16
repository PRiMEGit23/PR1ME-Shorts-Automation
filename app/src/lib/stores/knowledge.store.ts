/**
 * Knowledge store — Script Workbench slice (IMPLEMENTATION_PLAN 2S3):
 * browsable window of the knowledge base (or read-only topics), category /
 * difficulty filters, sort, column visibility, validation report + row
 * issues, and the row editor draft. Stores only apply state; services call
 * the bridge; the VM orchestrates (PRODUCT_LAYER §4/§5).
 */

import type {
	KnowledgeRow,
	KnowledgeSource,
	RowIssues,
	ValidationReport
} from '$lib/models/knowledge';
import { KNOWLEDGE_COLUMNS, TOPICS_COLUMNS } from '$lib/models/knowledge';

export type SortDir = 'asc' | 'desc';

export interface SortSpec {
	column: string;
	dir: SortDir;
}

export interface EditorState {
	open: boolean;
	isNew: boolean;
	rowIndex: number | null;
	original: KnowledgeRow;
	draft: KnowledgeRow;
}

const BLANK_EDITOR: EditorState = {
	open: false,
	isNew: false,
	rowIndex: null,
	original: {},
	draft: {}
};

// ------------------------------------------------------- pure helpers

/** In-memory category + difficulty filters (empty = keep). */
export function filterRows(
	rows: KnowledgeRow[],
	category: string | null,
	difficulty: string | null
): KnowledgeRow[] {
	return rows.filter((row) => {
		if (category && row.category !== category) return false;
		if (difficulty && row.difficulty !== difficulty) return false;
		return true;
	});
}

/** Stable string sort; empty cells sink to the end. */
export function sortRows(rows: KnowledgeRow[], sort: SortSpec | null): KnowledgeRow[] {
	if (!sort) return rows;
	const { column, dir } = sort;
	const sign = dir === 'asc' ? 1 : -1;
	return [...rows].sort((a, b) => {
		const va = (a[column] ?? '').toLowerCase();
		const vb = (b[column] ?? '').toLowerCase();
		if (!va && !vb) return 0;
		if (!va) return 1;
		if (!vb) return -1;
		if (va < vb) return -1 * sign;
		if (va > vb) return 1 * sign;
		return 0;
	});
}

/** Client-side window (virtualization over the filtered+sorted set). */
export function windowSlice<T>(rows: T[], offset: number, size: number): T[] {
	const start = Math.max(0, Math.min(offset, rows.length));
	const end = Math.min(start + size, rows.length);
	return rows.slice(start, end);
}

/** Distinct sorted values for a filter column (topics first, 3-digit ints). */
export function distinctValues(rows: KnowledgeRow[], column: string): string[] {
	const seen = new Set<string>();
	for (const row of rows) {
		const v = (row[column] ?? '').trim();
		if (v) seen.add(v);
	}
	return [...seen].sort((a, b) => {
		const na = Number(a);
		const nb = Number(b);
		if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
		return a.localeCompare(b);
	});
}

// ------------------------------------------------------------- store

export class KnowledgeStore {
	source: KnowledgeSource = $state('knowledge');
	header: string[] = $state([...KNOWLEDGE_COLUMNS]);
	/** All rows for the current source (backend caps at 10k/page). */
	allRows: KnowledgeRow[] = $state([]);
	total = $state(0);
	query = $state('');
	categoryFilter: string | null = $state(null);
	difficultyFilter: string | null = $state(null);
	sort: SortSpec | null = $state(null);
	visibleColumns: string[] = $state([...KNOWLEDGE_COLUMNS]);
	windowOffset = $state(0);
	windowSize = $state(200);

	loading = $state(false);
	searching = $state(false);
	/** Row highlighted in the gallery/table (Cmd+E opens it). */
	selected: number | null = $state(null);
	/** Pending unsaved changes (committed edits, new rows, deletions). */
	tableDirty = $state(false);
	/** Save with validation errors? (blocked unless explicitly overridden). */
	allowSaveWithErrors = $state(false);

	validation: ValidationReport | null = $state(null);
	/** Issues keyed by 0-based row index into `allRows` (file order). */
	rowIssues: RowIssues = $state(new Map());

	editor: EditorState = $state({ ...BLANK_EDITOR });

	/** Visible window: filter → sort → slice. */
	visible = $derived(
		windowSlice(
			sortRows(filterRows(this.allRows, this.categoryFilter, this.difficultyFilter), this.sort),
			this.windowOffset,
			this.windowSize
		)
	);

	/** All categories/difficulties present in the loaded table. */
	categories = $derived(distinctValues(this.allRows, 'category'));
	difficulties = $derived(distinctValues(this.allRows, 'difficulty'));

	/** Validation summary for the KB health panel. */
	validationSummary = $derived.by(() => {
		const report = this.validation;
		if (!report) return null;
		const errorRows = new Set(report.errors.map((e) => e.row));
		return {
			valid: report.valid,
			checkedAt: report.checkedAt,
			errors: report.errors.length,
			warnings: report.warnings.length,
			invalidRows: errorRows.size
		};
	});

	/** Rows are loaded in file order unless a search query is active. */
	canMapIssuesToRows = $derived(this.query.trim() === '');

	/* ------------------------------------------------- mutators */

	setSource(source: KnowledgeSource): void {
		if (source === this.source) return;
		this.source = source;
		this.header = source === 'knowledge' ? [...KNOWLEDGE_COLUMNS] : [...TOPICS_COLUMNS];
		this.allRows = [];
		this.total = 0;
		this.query = '';
		this.categoryFilter = null;
		this.difficultyFilter = null;
		this.sort = null;
		this.visibleColumns = [...this.header];
		this.windowOffset = 0;
		this.tableDirty = false;
		this.validation = null;
		this.rowIssues = new Map();
	}

	applyPage(rows: KnowledgeRow[], total: number): void {
		this.allRows = rows;
		this.total = total;
		this.windowOffset = 0;
		this.selected = null;
		this.loading = false;
		this.searching = false;
	}

	select(index: number | null): void {
		this.selected = index;
	}

	setQuery(query: string): void {
		this.query = query;
		this.windowOffset = 0;
	}

	setCategory(category: string | null): void {
		this.categoryFilter = category;
		this.windowOffset = 0;
	}

	setDifficulty(difficulty: string | null): void {
		this.difficultyFilter = difficulty;
		this.windowOffset = 0;
	}

	toggleSort(column: string): void {
		if (this.sort?.column === column) {
			this.sort = this.sort.dir === 'asc' ? { column, dir: 'desc' } : null;
		} else {
			this.sort = { column, dir: 'asc' };
		}
		this.windowOffset = 0;
	}

	toggleColumn(column: string): void {
		if (this.visibleColumns.includes(column)) {
			this.visibleColumns = this.visibleColumns.filter((c) => c !== column);
		} else {
			this.visibleColumns = [...this.visibleColumns, column];
		}
	}

	resetColumns(): void {
		this.visibleColumns = [...this.header];
	}

	advanceWindow(): void {
		this.windowOffset += this.windowSize;
	}

	/* ------------------------------------------------- validation */

	applyValidation(report: ValidationReport): void {
		this.validation = report;
		const issues: RowIssues = new Map();
		for (const issue of report.errors) {
			if (issue.row < 1) continue;
			const index = issue.row - 1;
			const list = issues.get(index) ?? [];
			list.push({ code: issue.code, column: issue.column, message: issue.message });
			issues.set(index, list);
		}
		this.rowIssues = issues;
	}

	clearValidation(): void {
		this.validation = null;
		this.rowIssues = new Map();
	}

	/* --------------------------------------------------- editor */

	openEditor(rowIndex: number, isNew = false): void {
		const sourceRow = this.allRows[rowIndex] ?? {};
		// Canonical copies: both draft and original carry every header column
		// so a pristine row is never reported dirty.
		const draft: KnowledgeRow = {};
		const original: KnowledgeRow = {};
		for (const col of this.header) {
			draft[col] = sourceRow[col] ?? '';
			original[col] = sourceRow[col] ?? '';
		}
		this.editor = {
			open: true,
			isNew,
			rowIndex: isNew ? null : rowIndex,
			original,
			draft
		};
	}

	closeEditor(): void {
		this.editor = { ...BLANK_EDITOR };
	}

	updateDraft(column: string, value: string): void {
		this.editor.draft[column] = value;
		this.editor = { ...this.editor, draft: { ...this.editor.draft } };
	}

	/** True when the draft differs from the original row. */
	editorDirty = $derived(
		this.editor.open && JSON.stringify(this.editor.draft) !== JSON.stringify(this.editor.original)
	);

	/** Commit the editor draft into `allRows` (new rows append). */
	commitDraft(): void {
		if (!this.editor.open) return;
		if (this.editor.isNew || this.editor.rowIndex === null) {
			this.allRows = [...this.allRows, { ...this.editor.draft }];
		} else {
			const index = this.editor.rowIndex;
			this.allRows = this.allRows.map((row, i) => (i === index ? { ...this.editor.draft } : row));
		}
		this.total = Math.max(this.total, this.allRows.length);
		this.tableDirty = true;
		this.clearValidation();
		this.closeEditor();
	}

	/** Duplicate a row: open the editor with a fresh clone (saved on commit). */
	duplicateRow(rowIndex: number): void {
		const sourceRow = this.allRows[rowIndex] ?? {};
		const draft: KnowledgeRow = {};
		for (const col of this.header) draft[col] = sourceRow[col] ?? '';
		this.editor = {
			open: true,
			isNew: true,
			rowIndex: null,
			original: {},
			draft
		};
	}
	/** Delete a row (kept unsaved until the table is saved). */
	deleteRow(rowIndex: number): void {
		this.allRows = this.allRows.filter((_, i) => i !== rowIndex);
		this.total = Math.max(0, this.total - 1);
		this.tableDirty = true;
		this.clearValidation();
		const issues = new Map(this.rowIssues);
		issues.delete(rowIndex);
		this.rowIssues = issues;
	}

	/** Table persisted — drop dirty + pending editor. */
	markSaved(): void {
		this.tableDirty = false;
		this.closeEditor();
	}
}

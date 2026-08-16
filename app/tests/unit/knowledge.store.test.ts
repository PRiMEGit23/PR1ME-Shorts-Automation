/**
 * knowledge store — pure filter/sort/window helpers + store lifecycle:
 * load, search state, edit buffer (open/commit/duplicate/delete), dirty
 * tracking, validation report mapping (IMPLEMENTATION_PLAN 2S3 §5).
 */

import { describe, expect, it } from 'vitest';
import { KnowledgeStore, filterRows, sortRows, windowSlice, distinctValues } from '$lib/stores/knowledge.store';
import type { KnowledgeRow } from '$lib/models/knowledge';

const ROW_A: KnowledgeRow = {
	topic: 'Bed Adhesion',
	difficulty: 'B',
	category: 'troubleshooting',
	subcategory: '',
	keywords: '["adhesion","bed level"]',
	search_intent: '',
	viewer_level: 'B',
	script: 'How to fix bed adhesion.',
	scene_count: '4',
	scene_plan_json: '[{"scene_id":1}]',
	title: 'Bed Adhesion Fix'
};

const ROW_B: KnowledgeRow = {
	topic: 'Infill Density',
	difficulty: 'I',
	category: 'slicer',
	subcategory: '',
	keywords: '["infill","density"]',
	search_intent: '',
	viewer_level: 'I',
	script: 'Infill density matters.',
	scene_count: '6',
	scene_plan_json: '[{"scene_id":1}]',
	title: 'Infill 101'
};

const ROW_C: KnowledgeRow = {
	topic: 'Z Offset',
	difficulty: 'A',
	category: 'troubleshooting',
	subcategory: '',
	keywords: '["z offset","first layer"]',
	search_intent: '',
	viewer_level: 'A',
	script: 'Dial in your Z offset.',
	scene_count: '5',
	scene_plan_json: '[{"scene_id":1}]',
	title: 'Z Offset Tuning'
};

const ALL = [ROW_A, ROW_B, ROW_C];

describe('pure helpers', () => {
	it('filterRows keeps rows matching category + difficulty', () => {
		expect(filterRows(ALL, 'troubleshooting', null)).toEqual([ROW_A, ROW_C]);
		expect(filterRows(ALL, null, 'I')).toEqual([ROW_B]);
		expect(filterRows(ALL, 'slicer', 'B')).toEqual([]);
		expect(filterRows(ALL, null, null)).toEqual(ALL);
	});

	it('sortRows is stable, case-insensitive, empty cells sink', () => {
		const empty = { ...ROW_B, topic: '' };
		const sorted = sortRows([empty, ROW_C, ROW_A], { column: 'topic', dir: 'asc' });
		expect(sorted.map((r) => r.topic)).toEqual(['Bed Adhesion', 'Z Offset', '']);
		const desc = sortRows(ALL, { column: 'topic', dir: 'desc' });
		expect(desc.map((r) => r.topic)).toEqual(['Z Offset', 'Infill Density', 'Bed Adhesion']);
	});

	it('windowSlice clamps offset and size', () => {
		expect(windowSlice(ALL, 1, 2)).toEqual([ROW_B, ROW_C]);
		expect(windowSlice(ALL, 10, 2)).toEqual([]);
		expect(windowSlice(ALL, 0, 100)).toEqual(ALL);
	});

	it('distinctValues dedupes and sorts numerically-aware', () => {
		const rows = [
			{ ...ROW_A, category: 'materials' },
			{ ...ROW_B, category: 'slicer' },
			{ ...ROW_C, category: 'slicer' }
		];
		expect(distinctValues(rows, 'category')).toEqual(['materials', 'slicer']);
	});
});

describe('KnowledgeStore lifecycle', () => {
	it('applies a page and derives the visible window', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		expect(store.total).toBe(3);
		expect(store.visible.length).toBe(3);
		expect(store.loading).toBe(false);
		expect(store.tableDirty).toBe(false);
	});

	it('applies category/difficulty filters + sort to the visible window', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.setCategory('troubleshooting');
		expect(store.visible.map((r) => r.topic)).toEqual(['Bed Adhesion', 'Z Offset']);
		store.setDifficulty('A');
		expect(store.visible.map((r) => r.topic)).toEqual(['Z Offset']);
		store.toggleSort('topic');
		expect(store.visible.map((r) => r.topic)).toEqual(['Z Offset']);
		store.toggleSort('topic'); // desc
		expect(store.visible.map((r) => r.topic)).toEqual(['Z Offset']);
		store.toggleSort('topic'); // clear
		expect(store.sort).toBeNull();
	});

	it('openEditor drafts a full row copy; updateDraft dirties it', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.openEditor(0);
		expect(store.editor.open).toBe(true);
		expect(store.editor.isNew).toBe(false);
		expect(store.editor.draft.topic).toBe('Bed Adhesion');
		expect(store.editorDirty).toBe(false);
		store.updateDraft('topic', 'Bed Adhesion Pro');
		expect(store.editorDirty).toBe(true);
		expect(store.editor.draft.topic).toBe('Bed Adhesion Pro');
	});

	it('commitDraft writes the row back, marks dirty, clears validation', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.openEditor(0);
		store.updateDraft('topic', 'Renamed');
		store.commitDraft();
		expect(store.allRows[0]!.topic).toBe('Renamed');
		expect(store.tableDirty).toBe(true);
		expect(store.editor.open).toBe(false);
	});

	it('duplicateRow opens a new-row editor with cloned values', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.duplicateRow(1);
		expect(store.editor.open).toBe(true);
		expect(store.editor.isNew).toBe(true);
		expect(store.editor.rowIndex).toBeNull();
		expect(store.editor.draft.topic).toBe('Infill Density');
		store.commitDraft();
		expect(store.allRows.length).toBe(4);
		expect(store.allRows[3]!.topic).toBe('Infill Density');
		expect(store.tableDirty).toBe(true);
	});

	it('deleteRow removes and decrements total', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.deleteRow(0);
		expect(store.allRows.map((r) => r.topic)).toEqual(['Infill Density', 'Z Offset']);
		expect(store.total).toBe(2);
		expect(store.tableDirty).toBe(true);
	});

	it('markSaved clears dirty and editor', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.openEditor(0, true);
		store.commitDraft();
		expect(store.tableDirty).toBe(true);
		store.markSaved();
		expect(store.tableDirty).toBe(false);
		expect(store.editor.open).toBe(false);
	});

	it('applyValidation maps 1-based rows to 0-based issue keys + summary', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.applyValidation({
			valid: false,
			checkedAt: '2026-01-01T00:00:00Z',
			errors: [
				{ row: 2, column: 'topic', code: 'duplicate_topic', message: 'duplicate topic' },
				{ row: 2, column: 'script', code: 'narration', message: '20-35s' }
			],
			warnings: [{ row: 1, column: 'keywords', code: 'few_keywords', message: 'min 3' }]
		});
		expect(store.rowIssues.get(1)?.length).toBe(2);
		expect(store.rowIssues.get(0)).toBeUndefined();
		expect(store.validationSummary).toEqual({
			valid: false,
			checkedAt: '2026-01-01T00:00:00Z',
			errors: 2,
			warnings: 1,
			invalidRows: 1
		});
		expect(store.canMapIssuesToRows).toBe(true);
	});

	it('setSource resets table + query + validation for topics', () => {
		const store = new KnowledgeStore();
		store.applyPage(ALL, 3);
		store.setQuery('infill');
		store.applyValidation({
			valid: false,
			checkedAt: 'x',
			errors: [],
			warnings: []
		});
		store.setSource('topics');
		expect(store.source).toBe('topics');
		expect(store.allRows.length).toBe(0);
		expect(store.total).toBe(0);
		expect(store.query).toBe('');
		expect(store.validation).toBeNull();
		expect(store.header.length).toBe(6);
	});
});

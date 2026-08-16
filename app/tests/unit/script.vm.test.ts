/**
 * script VM — orchestration over the mocked bridge: reload, debounced
 * search, validate-all, save gating, import preview flow, jump-to-row
 * (IMPLEMENTATION_PLAN 2S3 §5).
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { createServices } from '$lib/core/di';
import type { IpcTransport } from '$lib/core/bridge';
import { UiStore } from '$lib/stores/ui.store';
import { KnowledgeStore } from '$lib/stores/knowledge.store';
import { ScriptVm } from '$lib/viewmodels/script.vm';

const KB_PAGE = {
	header: ['topic', 'difficulty', 'category', 'keywords', 'scene_count', 'title'],
	rows: [
		['Bed Adhesion', 'B', 'troubleshooting', '["adhesion"]', '4', 'Bed Adhesion Fix'],
		['Infill', 'I', 'slicer', '["infill"]', '6', 'Infill 101']
	],
	total: 2
};

interface Ctx {
	vm: ScriptVm;
	ui: UiStore;
	store: KnowledgeStore;
	calls: string[];
	saved: { path: string | null; rows: string[][] | null };
}

function make(): Ctx {
	const calls: string[] = [];
	const saved: { path: string | null; rows: string[][] | null } = { path: null, rows: null };
	const transport = vi.fn(async (cmd: string, args: unknown) => {
		const a = args as Record<string, unknown>;
		calls.push(cmd);
		if (cmd === 'load_csv' || cmd === 'search_csv') {
			if (cmd === 'search_csv' && (a.query as string).trim() !== '') {
				return { ...KB_PAGE, rows: KB_PAGE.rows.slice(0, 1), total: 1 };
			}
			return KB_PAGE;
		}
		if (cmd === 'save_csv') {
			saved.path = a.path as string;
			saved.rows = a.rows as string[][];
			return { ok: true };
		}
		if (cmd === 'validate_csv') {
			return {
				valid: false,
				checkedAt: '2026-01-01T00:00:00Z',
				errors: [{ row: 1, column: 'topic', code: 'duplicate_topic', message: 'duplicate topic' }],
				warnings: []
			};
		}
		if (cmd === 'export_csv') return { ok: true };
		if (cmd === 'import_csv') {
			return {
				header: KB_PAGE.header,
				rows: KB_PAGE.rows,
				total: 2
			};
		}
		throw new Error(`unexpected cmd ${cmd}`);
	});
	const services = createServices(transport);
	const ui = new UiStore();
	const store = new KnowledgeStore();
	const vm = new ScriptVm(ui, store, services);
	return { vm, ui, store, calls, saved };
}

afterEach(() => {
	vi.useRealTimers();
});

describe('ScriptVm', () => {
	it('open loads the knowledge base into the store', async () => {
		const { vm, store, calls } = make();
		await vm.open();
		expect(calls).toContain('load_csv');
		expect(store.total).toBe(2);
		expect(store.allRows[0]?.topic).toBe('Bed Adhesion');
		expect(store.loading).toBe(false);
	});

	it('setSource reloads topics.csv with the topics header', async () => {
		const { vm, store } = make();
		await vm.setSource('topics');
		expect(store.source).toBe('topics');
		expect(store.total).toBe(2);
	});

	it('search is debounced and uses the backend search', async () => {
		vi.useFakeTimers();
		const { vm, store, calls } = make();
		await vm.open();
		calls.length = 0;
		vm.onSearch('inf');
		vi.advanceTimersByTime(350);
		await vi.runAllTimersAsync();
		expect(calls).toContain('search_csv');
		expect(store.total).toBe(1);
	});

	it('validate-all applies the report and errors surface via the store', async () => {
		const { vm, store } = make();
		await vm.open();
		await vm.validateAll();
		expect(store.validation?.valid).toBe(false);
		expect(store.validationSummary?.invalidRows).toBe(1);
		expect(store.rowIssues.get(0)?.map((i) => i.code)).toEqual(['duplicate_topic']);
	});

	it('save is blocked on validation errors unless overridden', async () => {
		const { vm, store, calls } = make();
		await vm.open();
		store.openEditor(0);
		store.commitDraft();
		expect(store.tableDirty).toBe(true);
		await vm.validateAll();
		const before = calls.filter((c) => c === 'save_csv').length;
		const ok = await vm.save();
		expect(ok).toBe(false);
		expect(calls.filter((c) => c === 'save_csv').length).toBe(before);
		store.allowSaveWithErrors = true;
		const ok2 = await vm.save();
		expect(ok2).toBe(true);
		expect(store.tableDirty).toBe(false);
		expect(calls.filter((c) => c === 'save_csv').length).toBe(before + 1);
	});

	it('save with no changes is a no-op info toast', async () => {
		const { vm, ui, calls } = make();
		await vm.open();
		const before = calls.filter((c) => c === 'save_csv').length;
		const ok = await vm.save();
		expect(ok).toBe(false);
		expect(calls.filter((c) => c === 'save_csv').length).toBe(before);
		expect(ui.toasts.at(-1)?.kind).toBe('info');
	});

	it('commitAndSave commits the editor draft then persists', async () => {
		const { vm, store, saved } = make();
		await vm.open();
		store.openEditor(1);
		store.updateDraft('title', 'Infill 201');
		store.allowSaveWithErrors = true;
		const ok = await vm.commitAndSave();
		expect(ok).toBe(true);
		expect(saved.rows?.[1]?.find((c) => c === 'Infill 201')).toBe('Infill 201');
		expect(store.editor.open).toBe(false);
	});

	it('jumpToRow aligns the window on the target row', async () => {
		const { vm, store } = make();
		await vm.open();
		store.windowSize = 1;
		vm.jumpToRow(2);
		expect(store.windowOffset).toBe(1);
	});

	it('import with no OS dialog support is a no-op (browser dev)', async () => {
		const { vm, calls } = make();
		const before = calls.length;
		await vm.import();
		expect(calls.length).toBe(before);
	});
});

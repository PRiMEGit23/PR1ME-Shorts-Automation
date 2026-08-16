/**
 * Knowledge service — CSV load/save/validate/import/export/search via the
 * bridge (PRODUCT_LAYER §4). Dialog pick/save uses the Tauri dialog plugin
 * only; browser dev falls back to the caller-provided path.
 */

import { open, save } from '@tauri-apps/plugin-dialog';

import type { Bridge } from '$lib/core/bridge';
import type { CsvPage, KnowledgeRow, ValidationReport } from '$lib/models/knowledge';
import { KNOWLEDGE_COLUMNS } from '$lib/models/knowledge';

const PAGE = 200;

export class KnowledgeService {
	constructor(private readonly bridge: Bridge) {}

	/** Paged read of `assets/<rel>` (windowed — 1000+ rows stay smooth). */
	async load(relPath: string, offset: number, limit: number = PAGE): Promise<CsvPage> {
		return this.bridge.load_csv(relPath, offset, limit);
	}

	/** Paged case-insensitive search of `assets/<rel>`. */
	async search(relPath: string, query: string, offset: number, limit: number = PAGE): Promise<CsvPage> {
		return this.bridge.search_csv(relPath, query, offset, limit);
	}

	/** Atomic write of the full table into `assets/<rel>`. */
	async save(relPath: string, rows: KnowledgeRow[]): Promise<void> {
		const header = [...KNOWLEDGE_COLUMNS];
		const table = rows.map((row) => header.map((col) => row[col] ?? ''));
		await this.bridge.save_csv(relPath, header, table);
	}

	/** Run `validate_knowledge_csv.py` over `assets/<rel>` (report relayed). */
	async validate(relPath: string): Promise<ValidationReport> {
		return this.bridge.validate_csv(relPath);
	}

	/** Preview an external CSV (import flow: preview → confirm → save). */
	async importPreview(path: string): Promise<CsvPage> {
		return this.bridge.import_csv(path);
	}

	/** Atomic export of the table to an external destination. */
	async exportTo(path: string, rows: KnowledgeRow[]): Promise<void> {
		const header = [...KNOWLEDGE_COLUMNS];
		const table = rows.map((row) => header.map((col) => row[col] ?? ''));
		await this.bridge.export_csv(path, header, table);
	}

	/** OS "open file" picker (Tauri only). Returns null when cancelled. */
	async pickImportPath(): Promise<string | null> {
		if (!('__TAURI_INTERNALS__' in window)) return null;
		return open({ multiple: false, filters: [{ name: 'CSV', extensions: ['csv'] }] });
	}

	/** OS "save file" picker (Tauri only). Returns null when cancelled. */
	async pickExportPath(): Promise<string | null> {
		if (!('__TAURI_INTERNALS__' in window)) return null;
		return save({
			defaultPath: 'knowledge-export.csv',
			filters: [{ name: 'CSV', extensions: ['csv'] }]
		});
	}
}

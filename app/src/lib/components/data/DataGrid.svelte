<script lang="ts">
	/**
	 * DataGrid — VDS §11: sticky `--label` header on `--surface-2`, 40 px
	 * rows, hover `--surface-3`, selected `--accent-soft` + 2 px left bar,
	 * numeric cells right-aligned, first column sticky, horizontal gridlines
	 * only, 6 px column resize (min 48 px), virtualized above 200 rows,
	 * ghost icon actions revealed on hover.
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import type { KnowledgeRow } from '$lib/models/knowledge';
	import type { SortSpec } from '$lib/stores/knowledge.store';
	import { windowSlice } from '$lib/stores/knowledge.store';

	type CellKind = 'text' | 'number' | 'badge';

	const BADGE_COLUMNS = new Set(['viewer_level', 'difficulty']);

	const cellKind = (column: string): CellKind => {
		if (column === 'scene_count') return 'number';
		if (BADGE_COLUMNS.has(column)) return 'badge';
		return 'text';
	};

	let {
		columns,
		rows,
		sort = null,
		selectedRow = null,
		rowIssues,
		onSort,
		onSelect,
		onEdit,
		onDelete
	}: {
		columns: string[];
		rows: KnowledgeRow[];
		sort?: SortSpec | null;
		selectedRow?: number | null;
		rowIssues: Map<number, { code: string; column: string; message: string }[]>;
		onSort: (column: string) => void;
		onSelect: (index: number) => void;
		onEdit: (index: number) => void;
		onDelete: (index: number) => void;
	} = $props();

	// --- column widths (6 px resize handle, min 48 px) ---
	let widths: Record<string, number> = $state({});
	const defaultWidth = (column: string) => (column === 'topic' || column === 'script' ? 240 : 150);
	const colWidth = (column: string) => widths[column] ?? defaultWidth(column);

	let resizing: string | null = $state(null);
	let resizeStartX = 0;
	let resizeStartW = 0;

	const startResize = (column: string, x: number) => {
		resizing = column;
		resizeStartX = x;
		resizeStartW = colWidth(column);
		window.addEventListener('pointermove', onResizeMove);
		window.addEventListener('pointerup', stopResize);
	};
	const onResizeMove = (e: PointerEvent) => {
		if (!resizing) return;
		widths[resizing] = Math.max(48, resizeStartW + (e.clientX - resizeStartX));
		widths = { ...widths };
	};
	const stopResize = () => {
		resizing = null;
		window.removeEventListener('pointermove', onResizeMove);
		window.removeEventListener('pointerup', stopResize);
	};

	// --- virtualization: render window around the first visible row ---
	const VIRTUAL_ABOVE = 200;
	const ROW_H = 40;
	let scrollTop = $state(0);
	const total = $derived(rows.length);
	const start = $derived(total > VIRTUAL_ABOVE ? Math.max(0, Math.floor(scrollTop / ROW_H) - 4) : 0);
	const end = $derived(
		total > VIRTUAL_ABOVE ? Math.min(total, start + Math.ceil(600 / ROW_H) + 8) : total
	);
	const visibleRows = $derived(windowSlice(rows, start, end - start));

	// row index in the virtualized list maps back to the full `rows` order
	const toFullIndex = (i: number) => start + i;
</script>

<div class="grid" onscroll={(e) => (scrollTop = e.currentTarget.scrollTop)}>
	<div class="header" style="min-width: {columns.reduce((s, c) => s + colWidth(c), 0)}px">
		{#each columns as column (column)}
			<div
				class="h-cell sortable"
				style="width: {colWidth(column)}px"
				role="columnheader"
				tabindex="0"
				onclick={() => onSort(column)}
				onkeydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						onSort(column);
					}
				}}
			>
				<span class="h-label">{column}</span>
				{#if sort?.column === column}
					<Icon name={sort.dir === 'asc' ? 'chevron-up' : 'chevron-down'} size={12} />
				{/if}
				<div
					class="resizer"
					role="separator"
					aria-orientation="vertical"
					onpointerdown={(e) => {
						e.stopPropagation();
						startResize(column, e.clientX);
					}}
				></div>
			</div>
		{/each}
	</div>
	<div class="body" style="min-width: {columns.reduce((s, c) => s + colWidth(c), 0)}px">
		{#if total > VIRTUAL_ABOVE}
			<div style="height: {start * ROW_H}px" aria-hidden="true"></div>
		{/if}
		{#each visibleRows as row, i (start + i)}
			{@const fullIndex = toFullIndex(i)}
			<div
				class="row"
				class:selected={selectedRow === fullIndex}
				class:invalid={(rowIssues.get(fullIndex)?.length ?? 0) > 0}
				style="height: {ROW_H}px"
				role="button"
				tabindex="0"
				onclick={() => onSelect(fullIndex)}
				onkeydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						onSelect(fullIndex);
					}
				}}
			>
				{#each columns as column (column)}
					{@const kind = cellKind(column)}
					<div class="cell" class:num={kind === 'number'} style="width: {colWidth(column)}px">
						{#if kind === 'badge'}
							<span class="badge" data-level={row[column]}>{row[column]}</span>
						{:else}
							<span class="t" title={row[column]}>{row[column]}</span>
						{/if}
						{#if column === 'topic'}
							<div class="actions">
								<IconButton
									icon="edit"
									label="Edit row"
									size={26}
									iconSize={13}
									onclick={(e) => {
										e.stopPropagation();
										onEdit(fullIndex);
									}}
								/>
								<IconButton
									icon="trash"
									label="Delete row"
									size={26}
									iconSize={13}
									danger
									onclick={(e) => {
										e.stopPropagation();
										onDelete(fullIndex);
									}}
								/>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/each}
		{#if total > VIRTUAL_ABOVE}
			<div style="height: {(total - end) * ROW_H}px" aria-hidden="true"></div>
		{/if}
	</div>
</div>

<style>
	.grid {
		height: 100%;
		overflow: auto;
		background: var(--surface-1);
	}
	.header,
	.row {
		display: flex;
	}
	.h-cell {
		position: relative;
		display: flex;
		align-items: center;
		gap: var(--space-1);
		padding: 0 var(--space-3);
		height: 40px;
		background: var(--surface-2);
		border-bottom: 1px solid var(--border-subtle);
		user-select: none;
	}
	.h-cell.sortable {
		cursor: pointer;
	}
	.h-label {
		font: var(--label);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-secondary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.resizer {
		position: absolute;
		right: -3px;
		top: 0;
		bottom: 0;
		width: 6px;
		cursor: col-resize;
	}
	.resizer:hover {
		background: var(--border-accent);
	}
	.header {
		position: sticky;
		top: 0;
		z-index: 2;
	}
	.row {
		border-bottom: 1px solid var(--border-subtle);
		transition: background-color var(--dur-fast) var(--ease-out);
	}
	.row:hover {
		background: var(--surface-3);
	}
	.row.selected {
		background: var(--table-row-selected);
		box-shadow: inset 2px 0 0 var(--accent);
	}
	.row.invalid .cell {
		box-shadow: inset 1px 0 0 var(--status-error);
	}
	.cell {
		position: relative;
		display: flex;
		align-items: center;
		gap: var(--space-1);
		padding: 0 var(--space-3);
		overflow: hidden;
	}
	.cell.num .t {
		margin-left: auto;
		font: var(--mono-sm);
		font-variant-numeric: var(--numeric);
	}
	.t {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font: var(--body-sm);
		color: var(--text-primary);
	}
	.actions {
		position: absolute;
		right: var(--space-1);
		top: 50%;
		transform: translateY(-50%);
		display: inline-flex;
		gap: 2px;
		opacity: 0;
		background: linear-gradient(to left, var(--surface-3), var(--surface-3) 70%, transparent);
		padding-left: var(--space-4);
	}
	.row:hover .actions,
	.row.selected .actions {
		opacity: 1;
	}
	.badge {
		display: inline-flex;
		align-items: center;
		height: var(--badge-h);
		padding: 0 var(--badge-px);
		border-radius: var(--badge-radius);
		font: var(--label);
		background: var(--chip-bg);
		border: 1px solid var(--chip-border);
		color: var(--text-secondary);
	}
	.badge[data-level='B'] {
		background: var(--status-ok-soft);
		color: var(--status-ok);
	}
	.badge[data-level='I'] {
		background: var(--status-info-soft);
		color: var(--status-info);
	}
	.badge[data-level='A'] {
		background: var(--status-warn-soft);
		color: var(--status-warn);
	}
</style>

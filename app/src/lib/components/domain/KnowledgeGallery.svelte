<script lang="ts">
	/**
	 * KnowledgeGallery — Script workbench surface (IMPLEMENTATION_PLAN 2S3):
	 * visual-first card grid (windowed virtualization), search + category /
	 * difficulty filters, table mode as secondary toggle (DataGrid), source
	 * toggle (knowledge base / read-only topics), validate-all with health
	 * summary + per-row error list + jump-to-row, import/export, add row.
	 */
	import Button from '$lib/components/primitives/Button.svelte';
	import EmptyState from '$lib/components/layout/EmptyState.svelte';
	import FilterChips from '$lib/components/data/FilterChips.svelte';
	import DataGrid from '$lib/components/data/DataGrid.svelte';
	import KnowledgeCard from '$lib/components/domain/KnowledgeCard.svelte';
	import SearchField from '$lib/components/data/SearchField.svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import { onMount } from 'svelte';
	import type { UiStore } from '$lib/stores/ui.store';
	import type { KnowledgeStore } from '$lib/stores/knowledge.store';
	import type { ScriptVm } from '$lib/viewmodels/script.vm';

	const CARD_W = 220;
	const CARD_H = 150;
	const GAP = 12;
	const CELL_W = CARD_W + GAP;
	const CELL_H = CARD_H + GAP;

	let {
		ui,
		store,
		vm
	}: { ui: UiStore; store: KnowledgeStore; vm: ScriptVm } = $props();

	// --- view state ---
	let view: 'grid' | 'table' = $state('grid');
	let columnsOpen = $state(false);

	// --- search (debounced in the VM) ---
	let query = $state('');
	$effect(() => {
		if (store.query !== query) query = store.query;
	});

	// --- windowed virtualization over the store's filtered+sorted set ---
	let scrollTop = $state(0);
	let viewportH = $state(600);
	let gridW = $state(0);

	onMount(() => {
		void vm.open();
	});

	const cols = $derived(Math.max(1, Math.floor((gridW + GAP) / CELL_W)));
	const gridRows = $derived(Math.ceil(store.visible.length / cols));
	const firstVisible = $derived(Math.max(0, Math.floor(scrollTop / CELL_H) * cols));
	const lastVisible = $derived(
		Math.min(store.visible.length, firstVisible + cols * (Math.ceil(viewportH / CELL_H) + 1))
	);
	const rendered = $derived(store.visible.slice(firstVisible, lastVisible));

	const cardIndex = (i: number) => {
		const full = firstVisible + i;
		return { full, col: full % cols, row: Math.floor(full / cols) };
	};
</script>

<div class="gallery">
	<!-- toolbar -->
	<div class="toolbar">
		<div class="t-group" role="group" aria-label="Source">
			<button
				class="seg"
				class:on={store.source === 'knowledge'}
				onclick={() => void vm.setSource('knowledge')}
			>
				Knowledge base
			</button>
			<button
				class="seg"
				class:on={store.source === 'topics'}
				onclick={() => void vm.setSource('topics')}
			>
				Topics
			</button>
		</div>

		<div class="t-search">
			<SearchField
				id="kb-search"
				placeholder="Search {store.source === 'knowledge' ? 'knowledge base' : 'topics'}"
				bind:value={query}
				oninput={() => vm.onSearch(query)}
				onkeydown={(e) => {
					if (e.key === 'Escape') vm.onSearch('');
				}}
			/>
		</div>

		<div class="t-spacer"></div>

		{#if store.source === 'knowledge'}
			<Button variant="primary" icon="plus" onclick={() => store.openEditor(0, true)}>
				Add row
			</Button>
			<Button icon="refresh" onclick={() => void vm.validateAll()} loading={ui.toasts.some((t) => t.kind === 'progress')}>
				Validate
			</Button>
			<IconButton icon="import" label="Import CSV" onclick={() => void vm.import()} />
			<IconButton icon="export" label="Export CSV" onclick={() => void vm.export()} />
			{#if store.tableDirty}
				<Button variant="primary" icon="check" onclick={() => void vm.save()}>
					Save
				</Button>
			{/if}
		{/if}

		<div class="t-divider" role="presentation"></div>

		<IconButton
			icon="grid"
			label="Grid view"
			size={28}
			iconSize={14}
			active={view === 'grid'}
			onclick={() => (view = 'grid')}
		/>
		<IconButton
			icon="table"
			label="Table view"
			size={28}
			iconSize={14}
			active={view === 'table'}
			onclick={() => (view = 'table')}
		/>
		{#if view === 'table'}
			<IconButton
				icon="columns"
				label="Column visibility"
				size={28}
				iconSize={14}
				active={columnsOpen}
				onclick={() => (columnsOpen = !columnsOpen)}
			/>
		{/if}
	</div>

	<!-- filters -->
	<div class="filters">
		<FilterChips
			label="Category filter"
			options={store.categories}
			selected={store.categoryFilter}
			onselect={(v) => store.setCategory(v)}
		/>
		<FilterChips
			label="Difficulty filter"
			options={store.difficulties}
			selected={store.difficultyFilter}
			onselect={(v) => store.setDifficulty(v)}
		/>
	</div>

	{#if view === 'table' && columnsOpen}
		<div class="colmenu">
			<button class="col-all" onclick={() => store.resetColumns()}>Reset columns</button>
			{#each store.header as column (column)}
				<label class="col-item">
					<input
						type="checkbox"
						checked={store.visibleColumns.includes(column)}
						onchange={() => store.toggleColumn(column)}
					/>
					<span>{column}</span>
				</label>
			{/each}
		</div>
	{/if}

	<!-- validation summary -->
	{#if store.validationSummary}
		<div class="health" class:invalid={!store.validationSummary.valid}>
			<Icon name={store.validationSummary.valid ? 'check' : 'warning'} size={13} />
			<span class="h-text">
				{#if store.validationSummary.valid}
					Valid
				{:else}
					{store.validationSummary.invalidRows} invalid row(s) · {store.validationSummary.errors} error(s)
				{/if}
				{#if store.validationSummary.warnings > 0}
					· {store.validationSummary.warnings} warning(s)
				{/if}
			</span>
			<span class="h-meta">
				checked {new Date(store.validationSummary.checkedAt).toLocaleTimeString()}
			</span>
			<IconButton
				icon="close"
				label="Dismiss validation summary"
				size={22}
				iconSize={12}
				onclick={() => store.clearValidation()}
			/>
		</div>
		{#if store.canMapIssuesToRows && store.validationSummary?.invalidRows}
			<div class="issues">
				{#each store.validation?.errors ?? [] as issue (issue.row + issue.code)}
					<button class="issue" onclick={() => vm.jumpToRow(issue.row)}>
						<span class="i-row">row {issue.row}</span>
						<span class="i-col">{issue.column}</span>
						<span class="i-msg">{issue.message}</span>
					</button>
				{/each}
			</div>
		{/if}
	{/if}

	<!-- body -->
	{#if store.loading}
		<EmptyState icon="refresh" title="Loading {store.source}…" />
	{:else if store.visible.length === 0}
		<EmptyState
			icon="search"
			title={store.query ? 'No matches' : `No rows`}
			subtitle={store.query ? `Nothing found for “${store.query}”` : 'Try clearing the filters'}
		>
			{#if store.query}
				<Button variant="ghost" onclick={() => store.setQuery('')}>Clear search</Button>
			{/if}
		</EmptyState>
	{:else if view === 'grid'}
		<div
			class="canvas"
			onscroll={(e) => (scrollTop = e.currentTarget.scrollTop)}
			bind:clientHeight={viewportH}
			bind:clientWidth={gridW}
		>
			<div class="spacer" style="height: {gridRows * CELL_H}px">
				{#each rendered as row, i (firstVisible + i)}
					{@const pos = cardIndex(i)}
					<div
						class="cell"
						style="left: {pos.col * CELL_W}px; top: {pos.row * CELL_H}px"
					>
					<KnowledgeCard
						row={row}
						selected={store.selected === pos.full}
						onclick={() => store.select(pos.full)}
					/>
					</div>
				{/each}
			</div>
		</div>
		<div class="meta"> {store.total} rows · {store.visible.length} shown</div>
	{:else}
		<div class="table-wrap">
			<DataGrid
				columns={store.visibleColumns}
				rows={store.visible}
				sort={store.sort}
				selectedRow={store.selected}
				rowIssues={store.rowIssues}
				onSort={(c) => store.toggleSort(c)}
				onSelect={(i) => store.select(i)}
				onEdit={(i) => store.openEditor(i)}
				onDelete={(i) => void vm.requestDelete(i)}
			/>
		</div>
	{/if}
</div>

<style>
	.gallery {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}
	.toolbar {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) var(--space-3);
		border-bottom: 1px solid var(--panel-border);
	}
	.t-group {
		display: inline-flex;
		height: 30px;
		padding: 2px;
		border-radius: var(--radius-full);
		background: var(--surface-3);
	}
	.seg {
		display: inline-flex;
		align-items: center;
		padding: 0 var(--space-3);
		border: none;
		border-radius: var(--radius-full);
		background: transparent;
		font: var(--label);
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--dur-base) var(--ease-out),
			color var(--dur-base) var(--ease-out);
	}
	.seg.on {
		background: var(--surface-4);
		border: 1px solid var(--border-strong);
		color: var(--text-primary);
	}
	.t-search {
		width: 260px;
	}
	.t-spacer {
		flex: 1;
	}
	.t-divider {
		width: 1px;
		height: 20px;
		background: var(--border-subtle);
		margin: 0 var(--space-1);
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		align-items: center;
		padding: var(--space-2) var(--space-3);
		border-bottom: 1px solid var(--panel-border);
	}
	.colmenu {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-3);
		padding: var(--space-2) var(--space-3);
		border-bottom: 1px solid var(--panel-border);
		background: var(--surface-2);
	}
	.col-item {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		font: var(--label);
		color: var(--text-secondary);
		cursor: pointer;
	}
	.col-all {
		border: none;
		background: transparent;
		font: var(--label);
		color: var(--accent);
		cursor: pointer;
		padding: 0;
	}
	.health {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-1) var(--space-3);
		border-bottom: 1px solid var(--panel-border);
		background: var(--status-ok-soft);
		color: var(--status-ok);
	}
	.health.invalid {
		background: var(--status-error-soft);
		color: var(--status-error);
	}
	.h-text {
		font: var(--body-sm);
		font-weight: 600;
	}
	.h-meta {
		flex: 1;
		font: var(--mono-xs);
		color: inherit;
		opacity: 0.7;
	}
	.issues {
		display: flex;
		flex-direction: column;
		max-height: 180px;
		overflow: auto;
		border-bottom: 1px solid var(--panel-border);
		background: var(--status-error-soft);
	}
	.issue {
		display: flex;
		gap: var(--space-2);
		align-items: baseline;
		padding: var(--space-1) var(--space-3);
		border: none;
		background: transparent;
		text-align: left;
		cursor: pointer;
		font: var(--body-sm);
		color: var(--text-primary);
	}
	.issue:hover {
		background: rgba(255, 255, 255, 0.04);
	}
	.i-row {
		font: var(--mono-xs);
		color: var(--status-error);
	}
	.i-col {
		font: var(--label);
		color: var(--text-secondary);
		min-width: 140px;
	}
	.i-msg {
		color: var(--text-secondary);
	}
	.canvas {
		flex: 1;
		overflow: auto;
		padding: var(--space-3);
	}
	.spacer {
		position: relative;
	}
	.cell {
		position: absolute;
		width: 220px;
		height: 150px;
	}
	.meta {
		padding: var(--space-1) var(--space-3);
		border-top: 1px solid var(--panel-border);
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
	.table-wrap {
		flex: 1;
		overflow: auto;
	}
</style>

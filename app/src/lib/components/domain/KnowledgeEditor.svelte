<script lang="ts">
	/**
	 * KnowledgeEditor — full-screen document (IMPLEMENTATION_PLAN 2S3 §3):
	 * 39 fields in 6 groups (KNOWLEDGE_GROUPS), JSON fields via JsonView,
	 * difficulty/viewer_level as B|I|A segmented, scene_count numeric,
	 * dirty state, inline validation errors (rowIssues), Cmd+D duplicate,
	 * prev/next row, discard confirm when dirty.
	 */
	import Badge from '$lib/components/primitives/Badge.svelte';
	import Button from '$lib/components/primitives/Button.svelte';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import JsonView from '$lib/components/data/JsonView.svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import { JSON_COLUMNS, KNOWLEDGE_GROUPS } from '$lib/models/knowledge';
	import type { UiStore } from '$lib/stores/ui.store';
	import type { KnowledgeStore } from '$lib/stores/knowledge.store';
	import type { ScriptVm } from '$lib/viewmodels/script.vm';

	const LONG_COLUMNS = new Set([
		'core_question',
		'learning_objective',
		'engineering_summary',
		'real_world_application',
		'common_misconceptions',
		'teaching_strategy',
		'script',
		'thumbnail_prompt',
		'thumbnail_negative_prompt',
		'negative_prompt',
		'camera_language',
		'lighting_style',
		'color_palette',
		'composition_style',
		'render_style',
		'description',
		'fact_check_notes'
	]);

	const LEVELS = ['B', 'I', 'A'];

	let {
		ui,
		store,
		vm
	}: { ui: UiStore; store: KnowledgeStore; vm: ScriptVm } = $props();

	const draft = $derived(store.editor.draft);
	const rowIssues = $derived.by<Map<string, string[]>>(() => {
		const issues = store.rowIssues.get(store.editor.rowIndex ?? -1);
		if (!issues) return new SvelteMap<string, string[]>();
		const byColumn = new SvelteMap<string, string[]>();
		for (const issue of issues) {
			const list = byColumn.get(issue.column) ?? [];
			list.push(issue.message);
			byColumn.set(issue.column, list);
		}
		return byColumn;
	});

	const errorsFor = (column: string): string[] => rowIssues.get(column) ?? [];
	const hasErrors = (column: string): boolean => errorsFor(column).length > 0;

	const isJson = (column: string): boolean => JSON_COLUMNS.includes(column);
	const isLong = (column: string): boolean => LONG_COLUMNS.has(column);
	const isLevel = (column: string): boolean =>
		column === 'difficulty' || column === 'viewer_level';

	const next = () => {
		if (store.editor.rowIndex === null) return;
		const nextIndex = Math.min(store.allRows.length - 1, store.editor.rowIndex + 1);
		if (nextIndex !== store.editor.rowIndex) store.openEditor(nextIndex);
	};

	const prev = () => {
		if (store.editor.rowIndex === null) return;
		const prevIndex = Math.max(0, store.editor.rowIndex - 1);
		if (prevIndex !== store.editor.rowIndex) store.openEditor(prevIndex);
	};

	/** Discard with confirm when the draft is dirty. */
	const discard = async () => {
		if (store.editorDirty) {
			const ok = await ui.askConfirm({
				title: 'Discard changes?',
				message: `Unsaved edits to “${draft.topic || 'this row'}” will be lost.`,
				confirmLabel: 'Discard',
				danger: true
			});
			if (!ok) return;
		}
		store.closeEditor();
	};

	const save = async () => {
		await vm.commitAndSave();
		if (!store.tableDirty) store.closeEditor();
	};

	const duplicate = () => {
		store.duplicateRow(store.editor.rowIndex ?? 0);
	};

	const deleteRow = () => {
		if (store.editor.rowIndex === null) return;
		void vm.requestDelete(store.editor.rowIndex).then(() => {
			if (store.editor.rowIndex !== null) store.closeEditor();
		});
	};
</script>

<div class="editor">
	<!-- document header -->
	<header class="doc-head">
		<div class="dh-left">
			<div class="dh-title">
				{#if store.editor.isNew}
					<span class="new-tag"><Icon name="plus" size={12} /> New row</span>
				{:else}
					<span class="dirty-tag" class:on={store.editorDirty}>
						<Icon name="dot" size={12} />
					</span>
				{/if}
				<span class="dh-topic">{draft.topic || 'Untitled'}</span>
				{#if store.editor.rowIndex !== null}
					<Badge status="muted">
						row {store.editor.rowIndex + 1} / {store.allRows.length}
					</Badge>
				{/if}
			</div>
			<div class="dh-sub">
				{#if store.editorDirty}
					<span class="dirty-label">unsaved changes</span>
				{:else}
					<span class="dirty-label clean">no changes</span>
				{/if}
			</div>
		</div>
		<div class="dh-actions">
			<IconButton icon="chevron-up" label="Previous row" size={28} iconSize={14} onclick={prev} />
			<IconButton icon="chevron-down" label="Next row" size={28} iconSize={14} onclick={next} />
			<IconButton icon="duplicate" label="Duplicate row" size={28} iconSize={14} onclick={duplicate} />
			<IconButton
				icon="trash"
				label="Delete row"
				size={28}
				iconSize={14}
				danger
				disabled={store.editor.isNew}
				onclick={deleteRow}
			/>
			<div class="dh-divider" role="presentation"></div>
			<Button variant="ghost" onclick={() => void discard()}>Cancel</Button>
			<Button variant="primary" icon="check" disabled={!store.editorDirty} onclick={() => void save()}>
				Save
			</Button>
		</div>
	</header>

	<!-- field groups -->
	<div class="doc-body">
		{#each KNOWLEDGE_GROUPS as group (group.name)}
			<section class="group">
				<h2 class="g-title">{group.name}</h2>
				<div class="g-grid">
					{#each group.columns as column (column)}
						<div class="field" class:span2={isLong(column) || isJson(column)} class:error={hasErrors(column)}>
							<label class="f-label" for="kb-{column}">{column}</label>
							{#if isLevel(column)}
								<div class="level" role="group" aria-label={column}>
									{#each LEVELS as level (level)}
										<button
											class="seg"
											class:on={draft[column] === level}
											onclick={() => store.updateDraft(column, level)}
											type="button"
										>
											{level}
										</button>
									{/each}
								</div>
							{:else if column === 'scene_count'}
								<input
									class="num"
									type="number"
									id="kb-{column}"
									min="0"
									value={draft[column]}
									oninput={(e) => store.updateDraft(column, e.currentTarget.value)}
								/>
							{:else if isJson(column)}
								<JsonView column={column} value={draft[column] ?? ''} onchange={(v) => store.updateDraft(column, v)} />
							{:else if isLong(column)}
								<textarea
									id="kb-{column}"
									rows="4"
									spellcheck="false"
									value={draft[column]}
									oninput={(e) => store.updateDraft(column, e.currentTarget.value)}
								></textarea>
							{:else}
								<input
									type="text"
									id="kb-{column}"
									spellcheck="false"
									value={draft[column]}
									oninput={(e) => store.updateDraft(column, e.currentTarget.value)}
								/>
							{/if}
							{#if hasErrors(column)}
								<div class="f-errors">
									{#each errorsFor(column) as message (message)}
										<span>{message}</span>
									{/each}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</section>
		{/each}
	</div>
</div>

<style>
	.editor {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}
	.doc-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
		padding: var(--space-2) var(--space-4);
		border-bottom: 1px solid var(--panel-border);
		background: var(--surface-2);
	}
	.dh-left {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.dh-title {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		min-width: 0;
	}
	.dh-topic {
		font: var(--title-md);
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.dirty-tag {
		display: inline-flex;
		color: var(--text-tertiary);
	}
	.dirty-tag.on {
		color: var(--status-warn);
	}
	.new-tag {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		height: var(--chip-h);
		padding: 0 var(--space-2);
		border-radius: var(--chip-radius);
		background: var(--accent-soft);
		font: var(--label);
		color: var(--text-primary);
	}
	.dh-sub {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}
	.dirty-label {
		font: var(--label);
		color: var(--status-warn);
	}
	.dirty-label.clean {
		color: var(--text-tertiary);
	}
	.dh-actions {
		display: flex;
		align-items: center;
		gap: var(--space-1);
	}
	.dh-divider {
		width: 1px;
		height: 20px;
		background: var(--border-subtle);
		margin: 0 var(--space-1);
	}
	.doc-body {
		flex: 1;
		overflow: auto;
		padding: var(--space-4);
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}
	.group {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
	.g-title {
		font: var(--label);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-secondary);
		margin: 0;
		padding-bottom: var(--space-1);
		border-bottom: 1px solid var(--border-subtle);
	}
	.g-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-3) var(--space-4);
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		min-width: 0;
	}
	.field.span2 {
		grid-column: span 2;
	}
	.f-label {
		font: var(--label);
		color: var(--text-secondary);
	}
	.field input[type='text'],
	.field textarea,
	.field .num {
		width: 100%;
		padding: var(--space-1) var(--space-3);
		border-radius: var(--radius-sm);
		border: 1px solid var(--input-border);
		background: var(--input-bg);
		font: var(--body-sm);
		color: var(--text-primary);
		outline: none;
		transition:
			border-color var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast) var(--ease-out);
	}
	.field input[type='text'] {
		height: var(--control-h);
	}
	.field textarea {
		resize: vertical;
		line-height: 1.5;
		min-height: 84px;
	}
	.field .num {
		width: 96px;
		height: var(--control-h);
		font: var(--mono-sm);
	}
	.field input:focus,
	.field textarea:focus {
		border-color: var(--input-focus-border);
		box-shadow: var(--ring);
	}
	.field.error input,
	.field.error textarea {
		border-color: var(--status-error);
	}
	.f-errors {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.f-errors span {
		font: var(--label);
		color: var(--status-error);
	}
	.level {
		display: inline-flex;
		gap: var(--space-1);
	}
	.seg {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 40px;
		height: var(--control-h);
		border: 1px solid var(--input-border);
		background: var(--input-bg);
		border-radius: var(--radius-sm);
		font: var(--mono-sm);
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out),
			border-color var(--dur-fast) var(--ease-out);
	}
	.seg.on {
		background: var(--accent-soft);
		border-color: var(--border-accent);
		color: var(--text-primary);
	}
</style>

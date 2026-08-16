<script lang="ts">
	/**
	 * EditorArea — editor tabs + content. Hosts the workbench host (slot).
	 * 2S1: empty ScriptDocument shell for the only document type.
	 */
	import EditorTabs from './EditorTabs.svelte';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import Button from '$lib/components/primitives/Button.svelte';
	import type { EditorStore, ScriptDocument } from '$lib/stores/editor.store';
	import type { UiStore } from '$lib/stores/ui.store';
	import type { Snippet } from 'svelte';

	let {
		editor,
		ui,
		children
	}: {
		editor: EditorStore;
		ui: UiStore;
		children?: Snippet;
	} = $props();

	function onEdit(doc: ScriptDocument, patch: Partial<ScriptDocument>) {
		editor.updateDocument<ScriptDocument>(doc.id, patch);
	}

	function save() {
		const doc = editor.active();
		if (!doc) return;
		editor.markDirty(doc.id, false);
		ui.pushToast('success', 'Script saved', { message: 'Document state is in-memory in 2S1.' });
	}

	const doc = $derived(editor.active()?.type === 'script' ? (editor.active() as ScriptDocument) : null);
</script>

<div class="editor-area">
	<EditorTabs {editor} />
	<div class="content">
		{@render children?.()}
	</div>
	{#if doc}
		<!-- empty ScriptDocument shell (2S1 §10) -->
		<div class="doc-sheet">
			<div class="sheet-head">
				<div class="sheet-title">
					<span class="sheet-kicker mono">script — draft</span>
					<h1 contenteditable="false" class="sheet-h1">{doc.title || 'Untitled script'}</h1>
				</div>
				<Button variant="primary" icon="check" onclick={save}>Save</Button>
			</div>
			<div class="sheet-meta">
				<label class="field">
					<span class="f-label">Topic</span>
					<input
						type="text"
						placeholder="e.g. Deep-sea anglerfish mating"
						value={doc.topic}
						oninput={(e) => onEdit(doc, { topic: e.currentTarget.value })}
					/>
				</label>
				<label class="field">
					<span class="f-label">Category</span>
					<input
						type="text"
						placeholder="e.g. Deep Sea"
						value={doc.category}
						oninput={(e) => onEdit(doc, { category: e.currentTarget.value })}
					/>
				</label>
				<label class="field f-narrow">
					<span class="f-label">Difficulty</span>
					<select
						value={doc.difficulty}
						onchange={(e) => onEdit(doc, { difficulty: e.currentTarget.value as ScriptDocument['difficulty'] })}
					>
						<option value="B">B</option>
						<option value="I">I</option>
						<option value="A">A</option>
					</select>
				</label>
			</div>
			<div class="sheet-body">
				<div class="sheet-body-head">
					<span class="sheet-kicker mono">narration</span>
					<span class="sheet-hint">Approx. 150–160 words / 65 s at 140 wpm — final word count lands in 2S3.</span>
				</div>
				<textarea
					class="narration"
					placeholder="Write the narration script…"
					value={doc.narration}
					oninput={(e) => onEdit(doc, { narration: e.currentTarget.value })}
				></textarea>
			</div>
		</div>
	{/if}
</div>

<style>
	.editor-area {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
		min-height: 0;
		background: var(--surface-0);
	}
	.content {
		flex: 1;
		min-width: 0;
		min-height: 0;
		display: flex;
		overflow: hidden;
	}
	.doc-sheet {
		flex: 1;
		min-width: 0;
		min-height: 0;
		overflow: auto;
		padding: var(--space-6) var(--space-7);
		background: var(--surface-0);
	}
	.sheet-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--space-4);
		margin-bottom: var(--space-5);
	}
	.sheet-title {
		min-width: 0;
	}
	.sheet-kicker {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-tertiary);
	}
	.sheet-h1 {
		margin: var(--space-1) 0 0;
		font: var(--display-xl);
		color: var(--text-primary);
	}
	.sheet-meta {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-4);
		margin-bottom: var(--space-6);
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		min-width: 240px;
	}
	.f-narrow {
		min-width: 120px;
	}
	.f-label {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.field input,
	.field select {
		height: var(--control-h);
		padding: 0 var(--space-3);
		border-radius: var(--radius-sm);
		border: 1px solid var(--input-border);
		background: var(--input-bg);
		font: var(--body-sm);
		color: var(--text-primary);
		outline: none;
	}
	.field input:focus,
	.field select:focus {
		border-color: var(--input-focus-border);
		box-shadow: var(--ring);
	}
	.field input::placeholder {
		color: var(--text-tertiary);
	}
	.sheet-body {
		max-width: 72ch;
	}
	.sheet-body-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--space-4);
		margin-bottom: var(--space-2);
	}
	.sheet-hint {
		font: var(--body-sm);
		color: var(--text-tertiary);
	}
	.narration {
		width: 100%;
		min-height: 360px;
		resize: vertical;
		padding: var(--space-4);
		border-radius: var(--radius-md);
		border: 1px solid var(--input-border);
		background: var(--input-bg);
		font: var(--body-md);
		line-height: 1.65;
		color: var(--text-primary);
		outline: none;
	}
	.narration:focus {
		border-color: var(--input-focus-border);
		box-shadow: var(--ring);
	}
	.narration::placeholder {
		color: var(--text-tertiary);
	}
</style>
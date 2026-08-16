<script lang="ts">
	/**
	 * EditorTabs — 36px tab strip (VDS §30/§35: editor-tab). Dirty dot;
	 * Ctrl+Tab / Ctrl+Shift+Tab cycling; Cmd+W / Cmd+Shift+T are global.
	 */
	import Icon, { type IconName } from '$lib/components/primitives/Icon.svelte';
	import type { EditorStore, DocumentType } from '$lib/stores/editor.store';

	let { editor }: { editor: EditorStore } = $props();

	const TYPE_ICON: Record<DocumentType, IconName> = {
		script: 'script',
		storyboard: 'storyboard',
		workflow: 'workflow',
		deliver: 'deliver'
	};

	function cycle(dir: 1 | -1) {
		if (editor.documents.length < 2) return;
		const i = editor.documents.findIndex((d) => d.id === editor.activeId);
		const next = (i + dir + editor.documents.length) % editor.documents.length;
		editor.activate(editor.documents[next]!.id);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.ctrlKey && e.key === 'Tab') {
			e.preventDefault();
			cycle(e.shiftKey ? -1 : 1);
		}
	}
</script>

{#if editor.documents.length > 0}
	<div class="tabs" role="tablist" tabindex="0" onkeydown={onKeydown}>
		{#each editor.documents as doc (doc.id)}
			<div
				class="tab"
				class:active={doc.id === editor.activeId}
				role="tab"
				aria-selected={doc.id === editor.activeId}
				tabindex="0"
				onclick={() => editor.activate(doc.id)}
				onkeydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						editor.activate(doc.id);
					}
				}}
			>
				<Icon name={TYPE_ICON[doc.type]} size={20} />
				<span class="t-label">{doc.title}</span>
				{#if doc.dirty}
					<span class="t-dirty" title="Unsaved changes"></span>
				{:else}
					<button
						class="t-close"
						aria-label="Close tab"
						onclick={(e) => {
							e.stopPropagation();
							editor.close(doc.id);
						}}
					>
						<Icon name="close" size={11} />
					</button>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.tabs {
		display: flex;
		align-items: stretch;
		height: var(--chrome-editor-tab);
		padding: 0 var(--space-2);
		gap: 2px;
		background: var(--surface-1);
		border-bottom: 1px solid var(--border-subtle);
		flex-shrink: 0;
		overflow: hidden;
	}
	.tab {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		max-width: 200px;
		padding: 0 var(--space-3);
		border: none;
		border-radius: var(--radius-sm) var(--radius-sm) 0 0;
		background: transparent;
		font: var(--body-sm);
		color: var(--text-secondary);
		cursor: pointer;
	}
	.tab:hover {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.tab.active {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.tab.active::after {
		content: '';
		position: absolute;
		left: var(--space-2);
		right: var(--space-2);
		bottom: 0;
		height: 2px;
		border-radius: 1px;
		background: var(--accent);
	}
	.t-label {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.t-dirty {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--accent);
		flex-shrink: 0;
	}
	.t-close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		padding: 0;
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-tertiary);
		cursor: pointer;
	}
	.t-close:hover {
		background: var(--surface-3);
		color: var(--text-primary);
	}
</style>
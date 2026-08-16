<script lang="ts">
	/**
	 * ConnectionCenter — 640×480 modal (VDS §935: modal, radius-lg,
	 * shadow-3): one panel, seven connection cards (UX §15). Opened by
	 * WorkbenchBar Connections, Cmd+Shift+D; closed by X, Escape, backdrop.
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import ConnectionCard from '$lib/components/layout/ConnectionCard.svelte';
	import { PROVIDERS } from '$lib/models/providers';
	import type { UiStore } from '$lib/stores/ui.store';
	import type { ProvidersStore } from '$lib/stores/providers.store';
	import type { ConnectionsVm } from '$lib/viewmodels/connections.vm';

	let { ui, store, vm }: { ui: UiStore; store: ProvidersStore; vm: ConnectionsVm } = $props();

	$effect(() => {
		if (ui.modal === 'connections') void vm.open();
	});
</script>

<div
	class="overlay"
	aria-hidden="true"
	tabindex="-1"
	onclick={(e) => {
		if (e.target === e.currentTarget) ui.closeModal();
	}}
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') ui.closeModal();
	}}
>
	<div
		class="center"
		role="dialog"
		aria-modal="true"
		aria-label="Connection Center"
	>
		<header class="head">
			<h2 class="title">Connection Center</h2>
			<span class="hint">Cmd+Shift+D</span>
			<button class="close" aria-label="Close" onclick={ui.closeModal}>
				<Icon name="close" size={16} />
			</button>
		</header>

		<div class="body">
			{#each PROVIDERS as p (p.id)}
				<ConnectionCard id={p.id} {vm} {store} />
			{/each}
		</div>

		<footer class="foot">
			<span class="note mono">Secrets stay masked and are written only to .env</span>
		</footer>
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: var(--z-modal);
		background: var(--overlay);
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.center {
		width: 640px;
		max-width: calc(100vw - var(--space-8));
		height: 480px;
		max-height: calc(100vh - var(--space-8));
		display: flex;
		flex-direction: column;
		background: var(--surface-1);
		border: 1px solid var(--border-strong);
		border-radius: var(--modal-radius);
		box-shadow: var(--modal-shadow);
		overflow: hidden;
	}
	.head {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		padding: var(--space-4);
		border-bottom: 1px solid var(--border-default);
		flex-shrink: 0;
	}
	.title {
		font: var(--title-lg);
		color: var(--text-primary);
		margin: 0;
	}
	.hint {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-tertiary);
		flex: 1;
	}
	.close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--control-h);
		height: var(--control-h);
		border: none;
		border-radius: var(--radius-md);
		background: transparent;
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out);
	}
	.close:hover {
		background: var(--surface-3);
		color: var(--text-primary);
	}
	.body {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		padding: var(--space-4);
		overflow-y: auto;
		flex: 1;
	}
	.foot {
		padding: var(--space-3) var(--space-4);
		border-top: 1px solid var(--border-default);
		flex-shrink: 0;
	}
	.note {
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
</style>
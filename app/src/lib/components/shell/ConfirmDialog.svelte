<script lang="ts">
	/**
	 * ConfirmDialog — modal confirm (VDS §935: overlay --overlay, --modal-*).
	 * Rendered by WindowShell when ui.confirm is set; Esc cancels.
	 */
	import { onMount } from 'svelte';
	import Button from '$lib/components/primitives/Button.svelte';
	import type { ConfirmRequest } from '$lib/stores/ui.store';

	let { confirm, onResolve }: { confirm: ConfirmRequest; onResolve: (ok: boolean) => void } =
		$props();

	onMount(() => {
		const target = confirm.danger ? 'confirm-primary' : 'confirm-cancel';
		document.querySelector<HTMLButtonElement>(`.${target}`)?.focus();
	});
</script>

<div
	class="scrim"
	role="presentation"
	onpointerdown={(e) => {
		if (e.target === e.currentTarget) onResolve(false);
	}}
	onkeydown={(e) => {
		if (e.key === 'Escape') onResolve(false);
	}}
>
	<div class="dialog" role="alertdialog" aria-modal="true" aria-label={confirm.title}>
		<div class="d-title">{confirm.title}</div>
		{#if confirm.message}
			<div class="d-message">{confirm.message}</div>
		{/if}
		<div class="d-actions">
			<Button variant="ghost" class="confirm-cancel" onclick={() => onResolve(false)}>
				{confirm.cancelLabel}
			</Button>
			<Button
				variant={confirm.danger ? 'danger' : 'primary'}
				class="confirm-primary"
				onclick={() => onResolve(true)}
			>
				{confirm.confirmLabel}
			</Button>
		</div>
	</div>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: var(--z-modal);
		background: var(--overlay);
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.dialog {
		width: 380px;
		max-width: calc(100vw - var(--space-6));
		background: var(--modal-bg);
		border: 1px solid var(--border-default);
		border-radius: var(--modal-radius);
		box-shadow: var(--modal-shadow);
		padding: var(--space-4);
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
	.d-title {
		font: var(--title-md);
		color: var(--text-primary);
	}
	.d-message {
		font: var(--body-sm);
		color: var(--text-secondary);
		line-height: 1.5;
	}
	.d-actions {
		display: flex;
		justify-content: flex-end;
		gap: var(--space-2);
		margin-top: var(--space-1);
	}
</style>

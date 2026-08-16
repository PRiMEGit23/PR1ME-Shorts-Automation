<script lang="ts">
	/**
	 * Toast — VDS §35: toast (glass, auto-dismiss 4s, errors persist, hover pauses).
	 */
	import Icon, { type IconName } from './Icon.svelte';
	import type { ToastItem } from '$lib/stores/ui.store';

	let {
		item,
		ondismiss
	}: {
		item: ToastItem;
		ondismiss: () => void;
	} = $props();

	let timer: ReturnType<typeof setTimeout> | null = null;

	const ICONS: Record<ToastItem['kind'], IconName> = {
		success: 'check',
		error: 'close',
		info: 'info',
		progress: 'refresh'
	};

	function arm() {
		if (item.ttl > 0) {
			timer = setTimeout(ondismiss, item.ttl);
		}
	}
	function disarm() {
		if (timer) {
			clearTimeout(timer);
			timer = null;
		}
	}

	$effect(() => {
		arm();
		return disarm;
	});
</script>

<div class="toast" data-kind={item.kind} onmouseenter={disarm} onmouseleave={arm} role="status">
	<span class="t-icon">
		{#if item.kind === 'progress'}
			<span class="spinner" aria-hidden="true"></span>
		{:else}
			<Icon name={ICONS[item.kind]} size={14} />
		{/if}
	</span>
	<div class="t-body">
		<div class="t-title">{item.title}</div>
		{#if item.message}
			<div class="t-msg">{item.message}</div>
		{/if}
	</div>
	{#if item.action}
		<button class="t-action" onclick={item.action.run}>{item.action.label}</button>
	{/if}
	<button class="t-close" aria-label="Dismiss notification" onclick={ondismiss}>
		<Icon name="close" size={12} />
	</button>
</div>

<style>
	.toast {
		display: flex;
		align-items: flex-start;
		gap: var(--space-3);
		width: 320px;
		padding: var(--space-3);
		border-radius: var(--radius-lg);
		border: 1px solid var(--border-default);
		background: var(--glass-bg);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		box-shadow: var(--shadow-2);
		animation: rise var(--motion-normal) var(--ease-out) both;
	}
	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
	.t-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		flex-shrink: 0;
		border-radius: var(--radius-sm);
	}
	.toast[data-kind='success'] .t-icon {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.toast[data-kind='error'] .t-icon {
		background: var(--danger-soft);
		color: var(--danger);
	}
	.toast[data-kind='info'] .t-icon {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.t-body {
		flex: 1;
		min-width: 0;
	}
	.t-title {
		font: var(--body-sm-semibold);
		color: var(--text-primary);
	}
	.t-msg {
		margin-top: 2px;
		font: var(--body-xs);
		color: var(--text-secondary);
	}
	.t-action {
		border: none;
		background: transparent;
		padding: var(--space-1);
		font: var(--body-xs-semibold);
		color: var(--accent);
		cursor: pointer;
	}
	.t-action:hover {
		text-decoration: underline;
	}
	.t-close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
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
	.spinner {
		width: 13px;
		height: 13px;
		border: 1.5px solid currentColor;
		border-top-color: transparent;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
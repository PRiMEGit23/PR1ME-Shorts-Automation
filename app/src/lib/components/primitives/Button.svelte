<script lang="ts">
	/**
	 * Button — control 34px (VDS §30/§35), variants: cta / primary / secondary / ghost / danger.
	 */
	import Icon from './Icon.svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { IconName } from './Icon.svelte';

	type Variant = 'cta' | 'primary' | 'secondary' | 'ghost' | 'danger';

	let {
		variant = 'secondary',
		icon,
		iconSize = 16,
		loading = false,
		disabled = false,
		children,
		...rest
	}: HTMLButtonAttributes & {
		variant?: Variant;
		icon?: IconName;
		iconSize?: number;
		loading?: boolean;
		children?: import('svelte').Snippet;
	} = $props();
</script>

<button
	class="btn btn-{variant}"
	{disabled}
	{...rest}
>
	{#if loading}
		<span class="spinner" aria-hidden="true"></span>
	{:else if icon}
		<Icon name={icon} size={iconSize} />
	{/if}
	<span class="btn-label">{@render children?.()}</span>
</button>

<style>
	.btn {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		height: var(--control-h);
		padding: 0 var(--space-4);
		border-radius: var(--radius-sm);
		border: 1px solid transparent;
		font: var(--body-sm-semibold);
		color: var(--text-primary);
		cursor: pointer;
		user-select: none;
		transition:
			background-color var(--motion-fast) var(--ease-out),
			border-color var(--motion-fast) var(--ease-out),
			transform var(--motion-fast) var(--ease-out),
			color var(--motion-fast) var(--ease-out),
			box-shadow var(--motion-fast) var(--ease-out);
	}
	.btn:focus-visible {
		outline: 2px solid var(--focus-ring);
		outline-offset: 1px;
	}
	.btn:disabled {
		opacity: 0.45;
		cursor: default;
	}
	.btn:not(:disabled):active {
		transform: translateY(1px);
	}
	.btn-label {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
	}

	.btn-cta {
		background: var(--cta-bg);
		color: var(--text-primary);
		box-shadow: var(--shadow-cta);
	}
	.btn-cta:not(:disabled):hover {
		background: var(--cta-bg-hover);
	}
	.btn-cta:disabled {
		box-shadow: none;
	}

	.btn-primary {
		background: var(--btn-primary-bg);
		color: var(--btn-primary-text);
	}
	.btn-primary:not(:disabled):hover {
		background: var(--btn-primary-bg-hover);
	}

	.btn-secondary {
		background: var(--btn-secondary-bg);
		border-color: var(--btn-secondary-border);
	}
	.btn-secondary:not(:disabled):hover {
		background: var(--btn-secondary-bg-hover);
		border-color: var(--btn-secondary-border-hover);
	}

	.btn-ghost {
		background: transparent;
		color: var(--text-secondary);
	}
	.btn-ghost:not(:disabled):hover {
		background: var(--surface-2);
		color: var(--text-primary);
	}

	.btn-danger {
		background: var(--danger-soft);
		color: var(--danger);
	}
	.btn-danger:not(:disabled):hover {
		background: var(--danger);
		color: var(--text-primary);
	}

	.spinner {
		width: 14px;
		height: 14px;
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
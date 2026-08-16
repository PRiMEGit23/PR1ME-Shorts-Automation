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
		border-radius: var(--radius-md);
		border: 1px solid transparent;
		font: var(--body-sm);
		font-weight: 600;
		color: var(--text-primary);
		cursor: pointer;
		user-select: none;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			border-color var(--dur-fast) var(--ease-out),
			transform var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast) var(--ease-out);
	}
	.btn:focus-visible {
		outline: solid var(--focus-ring);
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
		background: var(--btn-primary-bg);
		color: var(--btn-primary-text);
		height: var(--btn-cta-h);
		padding: 0 var(--btn-cta-px);
	}
	.btn-cta:not(:disabled):hover {
		background: var(--btn-primary-hover);
	}
	.btn-cta:not(:disabled):active {
		background: var(--btn-primary-active);
	}

	.btn-primary {
		background: var(--btn-primary-bg);
		color: var(--btn-primary-text);
	}
	.btn-primary:not(:disabled):hover {
		background: var(--btn-primary-hover);
	}
	.btn-primary:not(:disabled):active {
		background: var(--btn-primary-active);
	}

	.btn-secondary {
		background: var(--btn-secondary-bg);
		border-color: var(--btn-secondary-border);
	}
	.btn-secondary:not(:disabled):hover {
		background: var(--btn-secondary-hover);
	}

	.btn-ghost {
		background: transparent;
		color: var(--text-secondary);
	}
	.btn-ghost:not(:disabled):hover {
		background: var(--btn-ghost-hover);
		color: var(--text-primary);
	}

	.btn-danger {
		background: var(--btn-danger-bg);
		color: var(--text-inverse);
	}
	.btn-danger:not(:disabled):hover {
		background: var(--btn-danger-hover);
	}

	.spinner {
		width: 16px;
		height: 16px;
		border: 1.5px solid currentColor;
		border-top-color: transparent;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
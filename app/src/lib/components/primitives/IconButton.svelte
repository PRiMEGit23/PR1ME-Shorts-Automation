<script lang="ts">
	/**
	 * IconButton — square icon control (VDS §30: control 34; toolbars 28–34).
	 */
	import Icon from './Icon.svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { IconName } from './Icon.svelte';

	let {
		icon,
		label,
		size = 34,
		iconSize = 16,
		active = false,
		disabled = false,
		danger = false,
		...rest
	}: HTMLButtonAttributes & {
		icon: IconName;
		label: string;
		size?: number;
		iconSize?: number;
		active?: boolean;
		danger?: boolean;
	} = $props();
</script>

<button
	class="icon-btn"
	class:active
	class:danger
	style="--size: {size}px"
	{disabled}
	aria-label={label}
	title={label}
	{...rest}
>
	<Icon name={icon} size={iconSize} />
</button>

<style>
	.icon-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--size);
		height: var(--size);
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out),
			transform var(--dur-fast) var(--ease-out);
	}
	.icon-btn:focus-visible {
		outline: solid var(--focus-ring);
		outline-offset: 1px;
	}
	.icon-btn:disabled {
		opacity: 0.45;
		cursor: default;
	}
	.icon-btn:not(:disabled):hover {
		background: var(--btn-ghost-hover);
		color: var(--text-primary);
	}
	.icon-btn:not(:disabled):active {
		transform: scale(0.94);
	}
	.icon-btn.active {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.icon-btn.danger:not(:disabled):hover {
		background: var(--status-error-soft);
		color: var(--status-error);
	}
</style>
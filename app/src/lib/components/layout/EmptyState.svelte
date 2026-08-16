<script lang="ts">
	/**
	 * EmptyState — centered placeholder (UX §21 pattern).
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import type { IconName } from '$lib/components/primitives/Icon.svelte';

	let {
		icon,
		title,
		subtitle,
		children
	}: {
		icon: IconName;
		title: string;
		subtitle?: string;
		children?: import('svelte').Snippet;
	} = $props();
</script>

<div class="empty">
	<div class="e-icon"><Icon name={icon} size={24} /></div>
	<div class="e-title">{title}</div>
	{#if subtitle}
		<div class="e-sub">{subtitle}</div>
	{/if}
	{#if children}
		<div class="e-actions">{@render children?.()}</div>
	{/if}
</div>

<style>
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-2);
		padding: var(--space-6);
		text-align: center;
	}
	.e-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: var(--text-tertiary);
		margin-bottom: var(--space-1);
	}
	.e-title {
		font: var(--title-md);
		color: var(--text-primary);
	}
	.e-sub {
		max-width: 44ch;
		font: var(--body-sm);
		color: var(--text-secondary);
		line-height: 1.5;
	}
	.e-actions {
		display: flex;
		gap: var(--space-2);
		margin-top: var(--space-2);
	}
</style>
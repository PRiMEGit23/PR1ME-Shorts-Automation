<script lang="ts">
	/**
	 * SearchField — 34px search input (VDS §35: input), Esc clears.
	 */
	import Icon from './Icon.svelte';
	import type { HTMLInputAttributes, KeyboardEventHandler } from 'svelte/elements';

	let {
		value = $bindable(''),
		placeholder = 'Search',
		onkeydown,
		...rest
	}: HTMLInputAttributes & { value?: string } = $props();

	const handleKeydown: KeyboardEventHandler<HTMLInputElement> = (e) => {
		if (e.key === 'Escape') {
			value = '';
			e.currentTarget.blur();
		}
		onkeydown?.(e);
	};
</script>

<div class="field">
	<Icon name="search" size={14} />
	<input type="text" {placeholder} bind:value onkeydown={handleKeydown} spellcheck="false" {...rest} />
</div>

<style>
	.field {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		height: var(--control-h);
		padding: 0 var(--space-3);
		border-radius: var(--radius-sm);
		border: 1px solid var(--input-border);
		background: var(--input-bg);
		color: var(--text-tertiary);
		transition:
			border-color var(--motion-fast) var(--ease-out),
			box-shadow var(--motion-fast) var(--ease-out);
	}
	.field:focus-within {
		border-color: var(--focus-ring);
		box-shadow: 0 0 0 2px var(--focus-ring-soft);
		color: var(--accent);
	}
	.field:focus-within input {
		color: var(--text-primary);
	}
	input {
		flex: 1;
		min-width: 0;
		height: 100%;
		border: none;
		background: transparent;
		font: var(--body-sm);
		color: var(--text-primary);
		outline: none;
	}
	input::placeholder {
		color: var(--text-tertiary);
	}
</style>
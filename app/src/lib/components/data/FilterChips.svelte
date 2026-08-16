<script lang="ts">
	/**
	 * FilterChips — filter bar (VDS §35 chip): "All" + one chip per value.
	 * Colored soft chips are reserved for the KnowledgeCard accent, so
	 * filters use the neutral chip surface.
	 */
	let {
		label,
		options,
		selected = null,
		onselect
	}: {
		label: string;
		options: string[];
		selected?: string | null;
		onselect: (value: string | null) => void;
	} = $props();
</script>

<div class="chips" role="group" aria-label={label}>
	<button class="chip" class:on={selected === null} onclick={() => onselect(null)}>All</button>
	{#each options as option (option)}
		<button class="chip" class:on={selected === option} onclick={() => onselect(option)}>
			{option}
		</button>
	{/each}
</div>

<style>
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
	}
	.chip {
		display: inline-flex;
		align-items: center;
		height: var(--chip-h);
		padding: 0 var(--space-2);
		border-radius: var(--chip-radius);
		border: 1px solid var(--chip-border);
		background: var(--chip-bg);
		font: var(--label);
		color: var(--text-secondary);
		cursor: pointer;
		user-select: none;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			border-color var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out);
	}
	.chip:hover {
		background: var(--surface-4);
		color: var(--text-primary);
	}
	.chip.on {
		background: var(--accent-soft);
		border-color: var(--border-accent);
		color: var(--text-primary);
	}
</style>

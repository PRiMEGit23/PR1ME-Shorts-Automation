<script lang="ts">
	/**
	 * KnowledgeCard — 220×150 (VDS §8): category chip (colored soft),
	 * difficulty badge, topic 2 lines, keyword tags (2 max), scene count
	 * mono. Cards never carry more than one accent element: the category
	 * chip is the accent; difficulty + scene count stay neutral/mono.
	 */
	import Badge from '$lib/components/primitives/Badge.svelte';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import type { KnowledgeRow } from '$lib/models/knowledge';

	/** Deterministic soft-color accent per category (no hardcoded hues). */
	const SOFT_PALETTE = [
		'var(--accent-soft-strong)',
		'var(--status-ok-soft)',
		'var(--status-warn-soft)',
		'var(--status-info-soft)',
		'var(--status-error-soft)',
		'var(--status-muted-soft)'
	];

	const accentFor = (category: string): string => {
		let hash = 0;
		for (const ch of category) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
		return SOFT_PALETTE[hash % SOFT_PALETTE.length]!;
	};

	let {
		row,
		selected = false,
		onclick
	}: {
		row: KnowledgeRow;
		selected?: boolean;
		onclick: () => void;
	} = $props();

	const category = $derived(row.category || 'uncategorized');
	const difficulty = $derived(row.difficulty || '');
	const keywords = $derived(
		row.keywords
			? row.keywords
					.split(/[;,]/)
					.map((k) => k.trim())
					.filter(Boolean)
					.slice(0, 2)
			: []
	);
	const accent = $derived(accentFor(category));
</script>

<button
	class="card"
	class:selected
	style="--chip-accent: {accent}"
	onclick={onclick}
	type="button"
>
	<div class="k-head">
		<span class="k-category">{category}</span>
		{#if difficulty}
			<Badge status={difficulty === 'B' ? 'ok' : difficulty === 'A' ? 'warn' : 'info'}>
				{difficulty}
			</Badge>
		{/if}
	</div>
	<div class="k-topic" title={row.topic}>{row.topic}</div>
	<div class="k-tags">
		{#each keywords as keyword (keyword)}
			<span class="k-tag">{keyword}</span>
		{/each}
	</div>
	<div class="k-foot">
		<span class="k-scenes">
			<Icon name="play" size={10} />
			{row.scene_count ?? '0'} scenes
		</span>
	</div>
</button>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		width: 220px;
		height: 150px;
		padding: var(--card-padding);
		background: var(--card-bg);
		border: 1px solid var(--card-border);
		border-radius: var(--card-radius);
		text-align: left;
		cursor: pointer;
		transition:
			border-color var(--dur-fast) var(--ease-out),
			transform var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast) var(--ease-out);
	}
	.card:hover {
		border-color: var(--card-hover-border);
		transform: translateY(-1.5px);
		box-shadow: var(--shadow-1);
	}
	.card.selected {
		border: 2px solid var(--accent-soft-strong);
		padding: calc(var(--card-padding) - 1px);
	}
	.k-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-1);
	}
	.k-category {
		display: inline-flex;
		align-items: center;
		height: var(--chip-h);
		padding: 0 var(--space-2);
		border-radius: var(--chip-radius);
		background: var(--chip-accent);
		font: var(--label);
		color: var(--text-primary);
		max-width: 70%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.k-topic {
		font: var(--title-md);
		color: var(--text-primary);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		line-height: 1.35;
	}
	.k-tags {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
	}
	.k-tag {
		display: inline-flex;
		align-items: center;
		height: var(--chip-h);
		padding: 0 var(--space-2);
		border-radius: var(--chip-radius);
		background: var(--chip-bg);
		border: 1px solid var(--chip-border);
		font: var(--label);
		color: var(--text-secondary);
	}
	.k-foot {
		margin-top: auto;
	}
	.k-scenes {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
</style>

<script lang="ts">
	/**
	 * WorkflowNode — 220 px graph node (VDS §13): 32 px header with 16 px
	 * icon + 12.5 px 600 name; body value rows 24 px (key tertiary mono-xs,
	 * value primary mono-xs); 8 px square ports on the header line.
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import type { GraphNode } from '$lib/models/storyboard';

	let {
		node,
		x,
		y,
		selected,
		connectedOut,
		connectedIn,
		onselect
	}: {
		node: GraphNode;
		x: number;
		y: number;
		selected: boolean;
		connectedOut: boolean;
		connectedIn: boolean;
		onselect: (additive: boolean) => void;
	} = $props();

	const NODE_W = 220;
	const HEADER_H = 32;

	function onPointerDown(e: PointerEvent) {
		e.stopPropagation();
	}
</script>

<div
	class="node"
	class:selected
	role="button"
	tabindex="0"
	style="left: {x}px; top: {y}px"
	onpointerdown={onPointerDown}
	onclick={(e) => onselect(e.metaKey || e.ctrlKey)}
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onselect(e.metaKey || e.ctrlKey);
		}
	}}
>
	{#if connectedIn}
		<span class="port in" title="input"></span>
	{/if}
	<div class="head">
		<Icon name={node.id === 'output' ? 'graph' : 'code'} size={16} />
		<span class="h-name">{node.label}</span>
	</div>
	<div class="body">
		{#each node.values as [key, value] (key + value)}
			<div class="row">
				<span class="rk mono">{key}</span>
				<span class="rv mono" title={value}>{value}</span>
			</div>
		{/each}
	</div>
	{#if connectedOut}
		<span class="port out" title="output"></span>
	{/if}
</div>

<style>
	.node {
		position: absolute;
		width: 220px;
		background: var(--surface-1);
		border: 1px solid var(--border-default);
		border-radius: 6px;
		cursor: pointer;
		user-select: none;
	}
	.node.selected {
		background: var(--accent-soft);
		border: 2px solid var(--accent);
	}
	.head {
		display: flex;
		align-items: center;
		gap: 6px;
		height: 32px;
		padding: 0 10px;
		background: var(--surface-3);
		border-radius: 5px 5px 0 0;
		color: var(--text-secondary);
	}
	.node.selected .head {
		color: var(--accent);
	}
	.h-name {
		font-size: 12.5px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.body {
		display: flex;
		flex-direction: column;
		padding: 2px 0;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 24px;
		padding: 0 10px;
		min-width: 0;
	}
	.rk {
		font-size: 10px;
		color: var(--text-tertiary);
		white-space: nowrap;
		flex-shrink: 0;
	}
	.rv {
		font-size: 10px;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex: 1;
		min-width: 0;
	}
	.port {
		position: absolute;
		top: 12px;
		width: 8px;
		height: 8px;
		background: var(--surface-0);
		border: 1px solid var(--border-default);
	}
	.port.in {
		left: -4px;
	}
	.port.out {
		right: -4px;
		background: var(--accent);
		border-color: var(--accent);
	}
</style>

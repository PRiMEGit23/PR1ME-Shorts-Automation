<script lang="ts">
	/**
	 * LogTail — auto-scrolling terminal-like log display.
	 * Only auto-scrolls when already at bottom (UX requirement).
	 */
import { onMount } from 'svelte';
import type { Bridge } from '$lib/core/bridge';

	const bridge = {} as Bridge;

	let autoScroll = $state(true);
	let logLines = $derived<string[]>([] as string[]);
	let scrollPosition = $state(0);

	onMount(() => {
		const container = document.querySelector('.log-tail-container');
		if (container) {
			container.scrollTop = container.scrollHeight;
		}
	});

	let lines = $derived(logLines);
	let canScroll = $derived(
		scrollPosition >= logLines.length - 20
	);

	function appendLine(line: string): void {
		logLines = [...logLines, line.trim()];
		if (logLines.length > 500) {
			logLines = logLines.slice(-500);
		}
		if (autoScroll && canScroll) {
			const container = document.querySelector('.log-tail-container');
			if (container) {
				container.scrollTop = container.scrollHeight;
			}
		}
	}

	function clear(): void {
		logLines = [];
	}
</script>

<div class="log-tail-container" style="height: 200px; overflow: auto; font-family: monospace; font-size: 12px; padding: var(--space-2);">
	{#each logLines as line (line)}
		<div class="log-line">{@html line}</div>
	{/each}
</div>

<style>
	.log-tail-container {
		--bg: var(--surface-0);
		--text: var(--text-primary);
	}
	.log-line {
		display: block;
	 white-space: pre-wrap;
	 overflow: hidden;
	 text-overflow: ellipsis;
	 padding: 2px 4px;
	 color: var(--text-primary);
	 font-size: 12px;
	 line-height: 1.4;
	 border-bottom: 1px solid var(--border-subtle);
	}
	.log-line:last-child {
		border-bottom: none;
	}
</style>
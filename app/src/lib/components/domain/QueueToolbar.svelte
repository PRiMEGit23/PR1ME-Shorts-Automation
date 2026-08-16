<script lang="ts">
	/**
	 * Queue Toolbar — Board/List toggle, History, Filters, Search, Refresh, Auto Scroll.
	 * Uses bridge.invoke() for all IPC (2S4 pattern).
	 */
	import type { Bridge } from '$lib/core/bridge';
import Button from '$lib/components/primitives/Button.svelte';
import Tooltip from '$lib/components/primitives/Tooltip.svelte';


	const bridge = {} as Bridge;

	let mode = $state('board' as 'board' | 'dashboard' | 'history');
	let showHistory = $state(false);

	// Mode toggle
	function setMode(m: 'board' | 'dashboard' | 'history'): void {
		mode = m;
	}

	function toggleHistory(): void {
		showHistory = !showHistory;
	}

	async function refreshQueue(): Promise<void> {
		const qs = await bridge.queue_status();
		// update local state
	}

	async function searchTopics(query: string): Promise<void> {
		// search via knowledge service
	}
</script>
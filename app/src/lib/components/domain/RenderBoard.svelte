<script lang="ts">
	/**
	 * Render Queue Board — three columns: Queued | Running | Completed
	 * Cards display thumbnail, title, progress, current stage, elapsed, eta, provider, retry count, publish state.
	 * Uses bridge.invoke() for all IPC (2S4 pattern).
	 */
	import type { Bridge } from '$lib/core/bridge';
import type { QueueItem, QueueStatus, HistoryRun, RenderProgress } from '$lib/models/render';
import Button from '$lib/components/primitives/Button.svelte';
import Badge from '$lib/components/primitives/Badge.svelte';
import Tooltip from '$lib/components/primitives/Tooltip.svelte';
import { QueueService } from '$lib/services/queue.service';

	const bridge = {} as Bridge;

	// Reactive state from bridge
	let queueStatus = $derived({ active: [], tick: 0 });
	let items = $derived<any[]>([]);
	let mode = $state('board' as 'board' | 'dashboard' | 'history');
	let selectedItem = $state<{ id: string } | null>(null);
	let showInspector = $state(false);

	// Initialize: fetch queue status + history on mount
	(async () => {
		const qs = await bridge.queue_status();
		const history = await bridge.render_history();
		queueStatus = qs;
		// items populated from history + status
	})();

	// Column computation
	let queued = $derived(
		items.filter((i) => i.status === 'pending')
	);
	let running = $derived(
		items.filter((i) => i.status === 'running')
	);
	let completed = $derived(
		items.filter((i) => i.status === 'completed')
	);

	// Card component
	function Card({ item, column }: { item: QueueItem; column: 'queued' | 'running' | 'completed' }) {
		const overallPct = $derived(item.overallPct ?? 0);
		const stageProgress = $derived(item.stageProgress ?? `${Math.round(overallPct / 6.66)} / 15`);
		const etaMs = $derived(item.etaMs ?? 0);
		const runtimeMs = $derived(item.runtimeMs ?? 0);
		const minutes = $derived(Math.max(1, Math.round(runtimeMs / 60000)));
		const estimatedRemaining = $derived(
			etaMs > 0 ? Math.max(1, Math.round(etaMs / 60000)) : null
		);
	}

	// Helper functions
	async function selectItem(id: string): void {
		selectedItem = { id };
		showInspector = true;
	}

	async function cancelRender(id: string): Promise<void> {
		const result = await bridge.cancel_render(id);
		if (result.ok) {
			// update local state
			const idx = items.findIndex((i) => i.id === id);
			if (idx > -1) items[idx].status = 'cancelled';
			showInspector = false;
		}
	}

	async function retryRender(id: string): Promise<void> {
		const result = await bridge.retry_render(id, 42);
		if (result.ok) {
			const idx = items.findIndex((i) => i.id === id);
			if (idx > -1) items[idx].status = 'retrying';
			showInspector = false;
		}
	}

	async function startRender(id: string): Promise<void> {
		const result = await bridge.resume_render({
			run_dir: '',
			topic: items.find((i) => i.id === id)?.topic ?? '',
			seed: 42,
			max_attempts: 3,
			publish: false,
		});
		if (result.ok) {
			showInspector = false;
		}
	}
</script>
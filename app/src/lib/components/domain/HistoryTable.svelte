<script lang="ts">
	/**
	 * History Table — search, sort, filter, replay, resume, duplicate, open folder, inspect.
	 * Uses bridge.invoke() for all IPC (2S4 pattern).
	 */
import type { Bridge } from '$lib/core/bridge';
import type { HistoryRun } from '$lib/models/render';
import Button from '$lib/components/primitives/Button.svelte';
import Tooltip from '$lib/components/primitives/Tooltip.svelte';
import Badge from '$lib/components/primitives/Badge.svelte';

	const bridge = {} as Bridge;

	let history = $derived<HistoryRun[]>([] as HistoryRun[]);
	let filterTopic = $state('' as string);
	let filterStatus = $state('' as string);

	// Initialize: fetch history on mount
	(async () => {
		const hist = await bridge.render_history();
		history = hist as HistoryRun[];
	})();

	let filtered = $derived(
		history.filter(
			(r) =>
				(!filterTopic || r.topic.toLowerCase().includes(filterTopic.toLowerCase())) &&
				(!filterStatus || r.status === filterStatus)
		)
	);

	async function replayRun(runId: string): Promise<void> {
		// switch to storyboard workbench with run context
	}

	async function resumeRun(runId: string): Promise<void> {
		const result = await bridge.resume_render({
			run_dir: '',
			topic: '',
			seed: 42,
			max_attempts: 3,
			publish: false,
		});
	}

	async function duplicateRun(runId: string): Promise<void> {
		// create new queue item with same topic, seed+1
	}

	async function openFolder(runId: string): Promise<void> {
		const result = await bridge.open_output_folder(runId);
	}
</script>
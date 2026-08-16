<script lang="ts">
	/**
	 * Render Inspector — metadata, timeline, current stage, logs, storyboard, workflow, QA, optimization, publish, artifacts.
	 * Uses bridge.invoke() for all IPC (2S4 pattern).
	 */
	import type { Bridge } from '$lib/core/bridge';
import type { HistoryRun, RenderProgress } from '$lib/models/render';
import Button from '$lib/components/primitives/Button.svelte';
import Tooltip from '$lib/components/primitives/Tooltip.svelte';
import Badge from '$lib/components/primitives/Badge.svelte';

	const bridge = {} as Bridge;

	let selectedRunId = $state<string | null>(null);
	let showInspector = $state(false);
	let currentStage = $state('pending' as string);
	let logLines = $derived<string[]>([] as string[]);
	let qaReport = $derived<any | null>(null);
	let publishStatus = $derived('dry-run' as string);

	// Select a run to inspect
	async function selectRun(runId: string): Promise<void> {
		selectedRunId = runId;
		showInspector = true;
		// fetch progress + metadata
		const prog = await bridge.render_progress(runId);
		if (prog) {
			currentStage = prog.status ?? 'pending';
			logLines = prog.log_tail ?? [];
		}
	}

	function closeInspector(): void {
		showInspector = false;
		selectedRunId = null;
	}

	async function refreshLogs(runId: string, tail: number = 50): Promise<void> {
		const result = await bridge.render_logs(runId, tail);
		if (result) {
			logLines = result.lines;
		}
	}

	async function togglePublish(runId: string): Promise<void> {
		// toggle publish state
	}
</script>
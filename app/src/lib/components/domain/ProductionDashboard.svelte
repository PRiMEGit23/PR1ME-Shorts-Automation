<script lang="ts">
	/**
	 * Production Dashboard — KPIs derived from IPC passthrough.
	 * Success Rate, Queue Size, Running Jobs, Today's Jobs,
	 * Average Runtime, Failed Jobs, Active Providers, ETA, Recent Activity.
	 * Uses bridge.invoke() for all IPC (2S4 pattern).
	 */
	import type { Bridge } from '$lib/core/bridge';
	import type { ProductionStats, DashboardStats, HistoryRun } from '$lib/models/render';
import Button from '$lib/components/primitives/Button.svelte';
import Badge from '$lib/components/primitives/Badge.svelte';
import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import { QueueService } from '$lib/services/queue.service';

	const bridge = {} as Bridge;

	// Reactive state from bridge
	let productionStats = $derived<ProductionStats>({} as ProductionStats);
	let dashboardStats = $derived<DashboardStats>({
		successRate: 0,
		currentRenders: 0,
		queueLength: 0,
		avgRenderDuration: 0,
		ETA: null,
		todayCounts: { completed: 0, failed: 0, running: 0, cancelled: 0 },
		activeWorkers: 0,
		gpuInfo: null,
	});

	// Initialize: fetch stats + history on mount
	(async () => {
		const ps = await bridge.production_stats();
		const history = await bridge.render_history();
		productionStats = ps;
		// Derive KPIs
		const total = history.length;
		const completed = history.filter((r) => r.status === 'completed').length;
		const failed = history.filter((r) => r.status === 'failed').length;
		const running = history.filter((r) => r.status === 'running').length;
		const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;
		const avgDuration =
			completed > 0
				? history
						.filter((r) => r.total_duration_ms && r.total_duration_ms > 0)
						.reduce((sum, r) => sum + r.total_duration_ms!, 0) /
						completed
				: 0;
		dashboardStats = {
			successRate,
			currentRenders: running,
			queueLength: total,
			avgRenderDuration: avgDuration,
			ETA: running > 0 ? Math.max(1, Math.round((avgDuration * running) / 60000)) : null,
			todayCounts: {
				completed: history.filter(
					(r) => r.finished_at && new Date(r.finished_at).setHours(0, 0, 0, 0) === new Date().setHours(0, 0, 0, 0)
				).length,
				failed: failed,
				running,
				cancelled: history.filter((r) => r.status === 'cancelled').length,
			},
			activeWorkers: 0, // placeholder
			gpuInfo: null, // placeholder
		};
	})();

	let successRate = $derived(dashboardStats.successRate);
	let queueSize = $derived(dashboardStats.queueLength);
	let runningJobs = $derived(dashboardStats.currentRenders);
	let todayJobs = $derived({
		completed: dashboardStats.todayCounts.completed,
		failed: dashboardStats.todayCounts.failed,
		running: dashboardStats.todayCounts.running,
	});
	let avgRuntime = $derived(dashboardStats.avgRenderDuration);
	let failedJobs = $derived(dashboardStats.todayCounts.failed);
	let activeProviders = $derived(dashboardStats.activeWorkers);
	let eta = $derived(dashboardStats.ETA);
</script>
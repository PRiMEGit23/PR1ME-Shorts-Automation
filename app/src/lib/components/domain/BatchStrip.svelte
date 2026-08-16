<script lang="ts">
	/**
	 * Batch Strip — batch progress with completed/remaining/failed counts, ETA, throughput.
	 */
import type { Bridge } from '$lib/core/bridge';
import Button from '$lib/components/primitives/Button.svelte';
import Badge from '$lib/components/primitives/Badge.svelte';

const bridge = {} as Bridge;

let { completed = 0, remaining = 0, failed = 0 } = $props();
let eta = $derived(remaining > 0 ? Math.max(1, Math.round((remaining * 2) / 60)) : 0); // estimate: 2 min per item
let throughput = $derived(0); // items per minute (placeholder)
</script>

<div class="batch-strip">
	<div class="batch-header">
		<span>Batch Progress</span>
		<div class="batch-counts">
			<Badge status="completed">{completed}</Badge>
			<Badge status="pending">{remaining}</Badge>
			<Badge status="failed">{failed}</Badge>
		</div>
	</div>
	<div class="batch-eta">
		ETA: {eta > 0 ? eta + ' min ETA' : 'ETA pending'}
	</div>
	<div class="batch-throughput">
		Throughput: {`${throughput}/min`}
	</div>
</div>
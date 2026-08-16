<script lang="ts">
	/**
	 * Badge — status chip (VDS §35: badge).
	 */
	type Status = 'ok' | 'warn' | 'error' | 'info' | 'muted';

	let { status = 'muted', children }: { status?: Status; children?: import('svelte').Snippet } = $props();
</script>

<span class="badge" data-status={status}>{@render children?.()}</span>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		height: var(--badge-h);
		padding: 0 var(--badge-px);
		border-radius: var(--badge-radius);
		font: var(--label);
		white-space: nowrap;
	}
	.badge[data-status='ok'] {
		background: var(--status-ok-soft);
		color: var(--status-ok);
	}
	.badge[data-status='warn'] {
		background: var(--status-warn-soft);
		color: var(--status-warn);
	}
	.badge[data-status='error'] {
		background: var(--status-error-soft);
		color: var(--status-error);
	}
	.badge[data-status='info'] {
		background: var(--status-info-soft);
		color: var(--status-info);
	}
	.badge[data-status='muted'] {
		background: var(--status-muted-soft);
		color: var(--status-muted);
	}
</style>
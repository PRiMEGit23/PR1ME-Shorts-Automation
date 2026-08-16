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
		height: 20px;
		padding: 0 var(--space-2);
		border-radius: var(--radius-sm);
		font: var(--body-xs-semibold);
		letter-spacing: 0.02em;
		white-space: nowrap;
	}
	.badge[data-status='ok'] {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.badge[data-status='warn'] {
		background: var(--warn-soft);
		color: var(--warn);
	}
	.badge[data-status='error'] {
		background: var(--danger-soft);
		color: var(--danger);
	}
	.badge[data-status='info'] {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.badge[data-status='muted'] {
		background: var(--surface-3);
		color: var(--text-secondary);
	}
</style>
<script lang="ts">
	/**
	 * StatusDot — 8px status dot (VDS §34: status palette). `pulse` for
	 * running/live states; `unknown` (muted) for not-yet-probed providers.
	 */
	type Status = 'ok' | 'warn' | 'error' | 'info' | 'unknown';

	let { status = 'unknown', size = 8, pulse = false }: { status?: Status; size?: number; pulse?: boolean } = $props();
</script>

<span class="dot" class:pulse style="--size: {size}px" data-status={status} role="status" aria-label={status}></span>

<style>
	.dot {
		display: inline-block;
		width: var(--size);
		height: var(--size);
		border-radius: 50%;
		flex-shrink: 0;
	}
	.dot[data-status='ok'] {
		background: var(--status-ok);
	}
	.dot[data-status='warn'] {
		background: var(--status-warn);
	}
	.dot[data-status='error'] {
		background: var(--status-error);
	}
	.dot[data-status='info'] {
		background: var(--status-info);
		animation: pulse var(--dur-pulse) var(--ease-in-out) infinite;
	}
	.dot[data-status='unknown'] {
		background: var(--text-tertiary);
	}
	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
			transform: scale(1);
		}
		50% {
			opacity: 0.45;
			transform: scale(0.8);
		}
	}
</style>
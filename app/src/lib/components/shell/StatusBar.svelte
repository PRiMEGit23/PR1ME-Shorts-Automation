<script lang="ts">
	/**
	 * StatusBar — 26px bar (VDS §5/§30): version, pr1me probe, queue ETA,
	 * provider dots (AMBIENT_PROVIDERS), Cmd+K hint.
	 */
	import Kbd from '$lib/components/primitives/Kbd.svelte';
	import StatusDot from '$lib/components/primitives/StatusDot.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import { AMBIENT_PROVIDERS, PROVIDERS } from '$lib/models/providers';
	import type { AppStore } from '$lib/stores/app.store';

	let { app }: { app: AppStore } = $props();
</script>

<footer class="statusbar">
	<div class="sb-left">
		<span class="sb-mono">v{APP_VERSION}</span>
		<span class="sb-sep"></span>
		<span class="sb-mono">
			pr1me {app.version?.version ?? '—'}
		</span>
	</div>
	<div class="sb-right">
		<span class="sb-mono sb-eta">eta —</span>
		<div class="sb-providers">
			{#each AMBIENT_PROVIDERS as id (id)}
				<Tooltip label={`${PROVIDERS.find((p) => p.id === id)?.label ?? id} — not probed yet`} below>
					<span class="sb-provider"><StatusDot status="unknown" size={6} /></span>
				</Tooltip>
			{/each}
		</div>
		<span class="sb-kbd"><Kbd>⌘K</Kbd></span>
	</div>
</footer>

<style>
	.statusbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: var(--chrome-status);
		padding: 0 var(--space-3);
		background: var(--surface-1);
		border-top: 1px solid var(--border-subtle);
		color: var(--text-tertiary);
		flex-shrink: 0;
		user-select: none;
	}
	.sb-left,
	.sb-right {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}
	.sb-mono {
		font: var(--mono-xs);
		color: var(--text-secondary);
	}
	.sb-eta {
		color: var(--text-tertiary);
	}
	.sb-sep {
		width: 1px;
		height: 14px;
		background: var(--border-default);
	}
	.sb-providers {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}
	.sb-provider {
		display: inline-flex;
	}
	.sb-kbd {
		display: inline-flex;
	}
</style>

<script lang="ts" module>
	import { APP_VERSION } from '$lib/core/config';
</script>
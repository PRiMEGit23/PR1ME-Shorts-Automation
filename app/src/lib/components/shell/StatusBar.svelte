<script lang="ts">
	/**
	 * StatusBar — 26px bar (VDS §5/§30): version, pr1me probe, queue ETA,
	 * provider dots (AMBIENT_PROVIDERS), Cmd+K hint.
	 */
	import Kbd from '$lib/components/primitives/Kbd.svelte';
	import StatusDot from '$lib/components/primitives/StatusDot.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import { AMBIENT_PROVIDERS, PROVIDERS, type ProviderId } from '$lib/models/providers';
	import type { AppStore } from '$lib/stores/app.store';
	import type { ProvidersStore } from '$lib/stores/providers.store';
	import type { UiStore } from '$lib/stores/ui.store';

	let { app, providers, ui }: { app: AppStore; providers: ProvidersStore; ui: UiStore } = $props();

	function dotFor(id: ProviderId) {
		const entry = providers.health[id];
		return entry.status === 'ok'
			? 'ok'
			: entry.status === 'checking'
				? 'info'
				: entry.status === 'error'
					? 'error'
					: 'unknown';
	}

	function labelFor(id: ProviderId) {
		const entry = providers.health[id];
		const name = PROVIDERS.find((p) => p.id === id)?.label ?? id;
		if (entry.status === 'unknown' || entry.status === 'checking') return `${name} — probing…`;
		const lat = entry.latencyMs != null ? ` · ${entry.latencyMs} ms` : '';
		return `${name} — ${entry.status}${lat}`;
	}
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
		<button
			class="sb-providers"
			title="Connection Center — Cmd+Shift+D"
			onclick={() => ui.openModal('connections')}
		>
			{#each AMBIENT_PROVIDERS as id (id)}
				<Tooltip label={labelFor(id)} below>
					<span class="sb-provider"><StatusDot status={dotFor(id)} pulse={providers.health[id].status === 'checking'} size={6} /></span>
				</Tooltip>
			{/each}
		</button>
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
		padding: 0 var(--space-2);
		height: 20px;
		border: 1px solid transparent;
		border-radius: var(--radius-sm);
		background: transparent;
		cursor: pointer;
		transition:
			border-color var(--dur-fast) var(--ease-out),
			background-color var(--dur-fast) var(--ease-out);
	}
	.sb-providers:hover {
		border-color: var(--border-default);
		background: var(--surface-2);
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
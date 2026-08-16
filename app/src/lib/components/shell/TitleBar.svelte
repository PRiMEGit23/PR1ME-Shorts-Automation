<script lang="ts">
	/**
	 * TitleBar — 40px custom title bar (VDS §8/§30). data-tauri-drag-region
	 * on the bar; window controls via Tauri API (browser dev: no-ops).
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import ApertureMark from '$lib/components/primitives/ApertureMark.svelte';
	import Kbd from '$lib/components/primitives/Kbd.svelte';
	import StatusDot from '$lib/components/primitives/StatusDot.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import { getCurrentWindow, type Window } from '@tauri-apps/api/window';
	import { AMBIENT_PROVIDERS, PROVIDERS, type ProviderId } from '$lib/models/providers';
	import type { UiStore } from '$lib/stores/ui.store';
	import type { ProvidersStore } from '$lib/stores/providers.store';

	let { ui, providers }: { ui: UiStore; providers: ProvidersStore } = $props();

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

	let win: Window | null = null;
	let isMax = $state(false);
	let isTauri = $state(false);

	$effect(() => {
		if ('__TAURI_INTERNALS__' in window) {
			isTauri = true;
			win = getCurrentWindow();
			win.isMaximized().then((v) => (isMax = v));
			const un = win.onResized(() => {
				win?.isMaximized().then((v) => (isMax = v));
			});
			return () => {
				un.then((fn) => fn());
			};
		}
	});

	function minimize() {
		void win?.minimize();
	}
	function toggleMaximize() {
		void win?.toggleMaximize();
	}
	function close() {
		void win?.close();
	}
</script>

<header class="titlebar" data-tauri-drag-region>
	<div class="tb-left" data-tauri-drag-region>
		<span class="tb-logo" title="PR1ME Studio">
			<ApertureMark size={20} />
			<span class="tb-wordmark">PR1ME</span>
			<span class="tb-studio">STUDIO</span>
		</span>
		<span class="tb-sep"></span>
		<button class="tb-production" disabled title="Production switcher arrives with 2S2">
			<span class="tb-prod-glyph">◆</span>
			<span>Production: —</span>
			<span class="tb-prod-caret">▾</span>
		</button>
	</div>

	<div class="tb-right" data-tauri-drag-region>
		<button
			class="tb-providers"
			title="Connection Center — Cmd+Shift+D"
			onclick={() => ui.openModal('connections')}
		>
			{#each AMBIENT_PROVIDERS as id (id)}
				<Tooltip label={labelFor(id)}>
					<span class="tb-provider">
						<StatusDot status={dotFor(id)} pulse={providers.health[id].status === 'checking'} size={7} />
					</span>
				</Tooltip>
			{/each}
		</button>
		<button class="tb-queue" title="Render queue — active runs appear here" disabled>
			<span class="tb-queue-label">(queue</span>
			<span class="tb-queue-count mono">0</span>
			<span class="tb-queue-label">)</span>
		</button>
		{#if ui.booted}
			<span class="tb-kbd-hint">
				<Kbd>⌘K</Kbd>
			</span>
		{/if}
		<div class="tb-winctrl">
			{#if isTauri}
				<IconButton icon="minimize" label="Minimize" size={34} iconSize={14} onclick={minimize} />
				<IconButton icon={isMax ? 'restore' : 'maximize'} label={isMax ? 'Restore' : 'Maximize'} size={34} iconSize={14} onclick={toggleMaximize} />
				<button class="tb-close" aria-label="Close" onclick={close}>
					<Icon name="close" size={14} />
				</button>
			{:else}
				<span class="tb-browser-note mono">browser preview</span>
			{/if}
		</div>
	</div>
</header>

<style>
	.titlebar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: var(--chrome-title);
		padding: 0 var(--space-2) 0 var(--space-3);
		background: var(--surface-0);
		border-bottom: 1px solid var(--border-subtle);
		user-select: none;
		flex-shrink: 0;
	}
	.tb-left,
	.tb-right {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}
	.tb-logo {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
	}
	.tb-wordmark {
		font-size: 20px;
		font-weight: 600;
		letter-spacing: 0.12em;
		color: var(--text-primary);
	}
	.tb-studio {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-tertiary);
	}
	.tb-sep {
		width: 1px;
		height: 18px;
		background: var(--border-default);
	}
	.tb-production {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		height: var(--control-h);
		padding: 0 var(--space-3);
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		font: var(--body-sm);
		color: var(--text-secondary);
	}
	.tb-prod-glyph {
		color: var(--accent);
	}
	.tb-prod-caret {
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
	.tb-providers {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: 0 var(--space-2);
		height: 26px;
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-sm);
		background: transparent;
		cursor: pointer;
		transition:
			border-color var(--dur-fast) var(--ease-out),
			background-color var(--dur-fast) var(--ease-out);
	}
	.tb-providers:hover {
		border-color: var(--border-strong);
		background: var(--surface-1);
	}
	.tb-provider {
		display: inline-flex;
		cursor: default;
	}
	.tb-queue {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		height: 26px;
		padding: 0 var(--space-3);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-sm);
		background: transparent;
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
	.tb-queue-label {
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.tb-queue-count {
		color: var(--text-primary);
	}
	.tb-kbd-hint {
		display: inline-flex;
	}
	.tb-winctrl {
		display: flex;
		align-items: center;
		gap: 2px;
		margin-right: -2px;
	}
	.tb-close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 34px;
		height: 34px;
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out);
	}
	.tb-close:hover {
		background: var(--status-error);
		color: var(--text-inverse);
	}
	.tb-browser-note {
		font: var(--mono-xs);
		color: var(--text-tertiary);
		padding: 0 var(--space-2);
	}
</style>
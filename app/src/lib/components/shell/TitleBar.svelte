<script lang="ts">
	/**
	 * TitleBar — 40px custom title bar (VDS §8/§30). data-tauri-drag-region
	 * on the bar; window controls via Tauri API (browser dev: no-ops).
	 */
	import IconButton from '$lib/components/primitives/IconButton.svelte';
	import Kbd from '$lib/components/primitives/Kbd.svelte';
	import StatusDot from '$lib/components/primitives/StatusDot.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import { getCurrentWindow, type Window } from '@tauri-apps/api/window';
	import type { UiStore } from '$lib/stores/ui.store';

	let { ui }: { ui: UiStore } = $props();

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

	const PROVIDERS = [
		{ id: 'ollama', label: 'Ollama — not probed yet' },
		{ id: 'comfyui', label: 'ComfyUI — not probed yet' },
		{ id: 'kokoro', label: 'Kokoro — not probed yet' },
		{ id: 'ffmpeg', label: 'FFmpeg — not probed yet' }
	];
</script>

<header class="titlebar" data-tauri-drag-region>
	<div class="tb-left" data-tauri-drag-region>
		<span class="tb-logo" title="PR1ME Studio">
			<span class="tb-logo-icon">1</span>
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
		<div class="tb-providers">
			{#each PROVIDERS as p (p.id)}
				<Tooltip label={p.label}>
					<span class="tb-provider">
						<StatusDot status="unknown" size={7} />
					</span>
				</Tooltip>
			{/each}
		</div>
		<button class="tb-queue" title="Render queue — active runs appear here" disabled>
			<span class="tb-queue-label">queue</span>
			<span class="tb-queue-count mono">0</span>
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
				<IconButton icon="close" label="Close" size={34} iconSize={14} danger onclick={close} />
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
		height: var(--titlebar-h);
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
	.tb-logo-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		border-radius: var(--radius-sm);
		background: var(--surface-3);
		border: 1px solid var(--border-default);
		font: var(--mono-sm);
		color: var(--accent);
	}
	.tb-wordmark {
		font: var(--title-sm);
		letter-spacing: 0.18em;
		color: var(--text-primary);
	}
	.tb-studio {
		font: var(--mono-xs);
		letter-spacing: 0.3em;
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
		font-size: 10px;
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
	}
	.tb-provider {
		display: inline-flex;
		cursor: default;
	}
	.tb-queue {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		height: 26px;
		padding: 0 var(--space-3);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-sm);
		background: transparent;
		font: var(--mono-xs);
		color: var(--text-tertiary);
	}
	.tb-queue-label {
		letter-spacing: 0.08em;
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
	.tb-browser-note {
		font-size: 10px;
		color: var(--text-tertiary);
		padding: 0 var(--space-2);
	}
</style>
<script lang="ts">
	/**
	 * StatusBar — 26px bar (VDS §30): version, pr1me probe, queue ETA,
	 * provider dots, Cmd+K hint.
	 */
	import Kbd from '$lib/components/primitives/Kbd.svelte';
	import StatusDot from '$lib/components/primitives/StatusDot.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import type { AppStore } from '$lib/stores/app.store';

	let { app }: { app: AppStore } = $props();

	const PROVIDERS = [
		{ id: 'ollama', label: 'Ollama' },
		{ id: 'comfyui', label: 'ComfyUI' },
		{ id: 'kokoro', label: 'Kokoro' },
		{ id: 'ffmpeg', label: 'FFmpeg' }
	];
</script>

<footer class="statusbar">
	<div class="sb-left">
		<span class="mono">v{APP_VERSION}</span>
		<span class="sb-sep"></span>
		<span class="mono">
			pr1me {app.version?.version ?? '—'}
		</span>
	</div>
	<div class="sb-right">
		<span class="mono sb-eta">eta —</span>
		<div class="sb-providers">
			{#each PROVIDERS as p (p.id)}
				<Tooltip label={`${p.label} — not probed yet`} below>
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
		height: var(--statusbar-h);
		padding: 0 var(--space-3);
		background: var(--surface-1);
		border-top: 1px solid var(--border-subtle);
		font-size: 11px;
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
	.mono {
		font-family: var(--font-mono);
		letter-spacing: 0.02em;
		color: var(--text-secondary);
	}
</style>

<script lang="ts" module>
	import { APP_VERSION } from '$lib/core/config';
</script>
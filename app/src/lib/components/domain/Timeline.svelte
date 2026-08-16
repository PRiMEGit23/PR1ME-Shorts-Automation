<script lang="ts">
	/**
	 * Timeline — horizontal scene timeline (2S4 Storyboard / UX §10): scene
	 * markers, deterministic plan durations (equal-width when the plan is
	 * unavailable), total runtime, selection. ←/→ moves the selection.
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import type { TimelineClip } from '$lib/stores/storyboard.store';
	import type { StoryboardVm } from '$lib/viewmodels/storyboard.vm';

	let {
		clips,
		totalRuntime,
		hasDurations,
		selectedSceneId,
		vm
	}: {
		clips: TimelineClip[];
		totalRuntime: number | null;
		hasDurations: boolean;
		selectedSceneId: string | null;
		vm: StoryboardVm;
	} = $props();

	/** px per second — fits the widest track into the viewport width. */
	const PX_PER_S = 12;

	function fmt(ms: number | null): string {
		if (ms === null) return '—';
		const s = ms / 1000;
		if (s < 60) return `${s.toFixed(1)}s`;
		return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
	}

	function fmtTotal(ms: number | null): string {
		if (ms === null) return '—';
		const s = ms / 1000;
		return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
	}

	const ticks = $derived.by(() => {
		if (!hasDurations || totalRuntime === null) return [];
		const seconds = Math.ceil(totalRuntime / 1000);
		const out: { s: number; major: boolean }[] = [];
		for (let s = 0; s <= seconds; s++) {
			if (s % 5 === 0 || s === seconds) out.push({ s, major: s % 5 === 0 });
		}
		return out;
	});

	function widthMs(durationMs: number | null): number {
		if (durationMs === null) return 200;
		return Math.max(48, (durationMs / 1000) * PX_PER_S);
	}

	function widthForClip(clip: TimelineClip): number {
		if (hasDurations) return widthMs(clip.durationMs);
		return 160;
	}

	function totalWidth(): number {
		if (hasDurations) {
			return clips.reduce((w, c) => w + widthMs(c.durationMs), 0) + clips.length * 4;
		}
		return clips.length * 164 + 4;
	}
</script>

<div class="timeline" role="list" aria-label="Scene timeline">
	<div class="head">
		<span class="label">TIMELINE</span>
		<span class="total mono">
			<Icon name="clock" size={12} /> {fmtTotal(totalRuntime)}
		</span>
		{#if !hasDurations}
			<span class="note mono">plan durations unavailable — equal-width segments</span>
		{/if}
	</div>
	<div class="track" style="width: {totalWidth()}px">
		<div class="ruler">
			{#if hasDurations}
				{#each ticks as tick (tick.s)}
					<span class="tick" class:major={tick.major} style="left: {tick.s * PX_PER_S}px">
						{#if tick.major}
							<span class="label mono">{tick.s}s</span>
						{/if}
					</span>
				{/each}
			{/if}
		</div>
		<div class="clips">
			{#each clips as clip (clip.sceneId)}
				<button
					class="clip mono"
					class:selected={clip.sceneId === selectedSceneId}
					style="width: {widthForClip(clip)}px"
					title={`${clip.label} · ${fmt(clip.durationMs)}`}
					onclick={() => vm.selectScene(clip.sceneId)}
				>
					<span class="marker">{clip.label}</span>
					<span class="dur">{fmt(clip.durationMs)}</span>
				</button>
			{/each}
		</div>
	</div>
</div>

<style>
	.timeline {
		background: var(--surface-1);
		border-top: 1px solid var(--border-subtle);
		overflow-x: auto;
		flex-shrink: 0;
	}
	.head {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		height: 28px;
		padding: 0 var(--space-4);
		border-bottom: 1px solid var(--border-subtle);
	}
	.label {
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 0.08em;
		color: var(--text-tertiary);
	}
	.total {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: 11px;
		color: var(--accent);
		font-variant-numeric: tabular-nums;
	}
	.note {
		font-size: 10px;
		color: var(--text-tertiary);
	}
	.track {
		position: relative;
		padding: 0 8px 10px;
	}
	.ruler {
		position: relative;
		height: 20px;
	}
	.tick {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 1px;
		background: var(--border-subtle);
	}
	.tick.major {
		background: var(--border-default);
	}
	.tick .label {
		position: absolute;
		top: 4px;
		left: 4px;
		font-size: 10px;
		color: var(--text-tertiary);
	}
	.clips {
		display: flex;
		gap: 4px;
	}
	.clip {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 4px;
		height: 24px;
		padding: 0 8px;
		border: 1px solid var(--border-default);
		border-radius: 4px;
		background: var(--surface-3);
		cursor: pointer;
		overflow: hidden;
	}
	.clip:hover {
		border-color: var(--border-strong);
	}
	.clip.selected {
		border: 2px solid var(--accent);
		padding: 0 7px;
	}
	.marker {
		font-size: 10px;
		color: var(--text-secondary);
		white-space: nowrap;
	}
	.dur {
		font-size: 10px;
		color: var(--text-tertiary);
		font-variant-numeric: tabular-nums;
	}
</style>

<script lang="ts">
	/**
	 * SceneCard — one scene on the SceneBoard (VDS §14 / UX §11): 200 px
	 * wide, 64×112 thumbnail area, candidate strip, camera/lighting/duration
	 * chips, lock glyph (order is script-locked), transition arrow to next.
	 */
	import { convertFileSrc } from '@tauri-apps/api/core';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import CandidateStrip from '$lib/components/domain/CandidateStrip.svelte';
	import type { SceneView } from '$lib/stores/storyboard.store';
	import type { StoryboardVm } from '$lib/viewmodels/storyboard.vm';

	let {
		view,
		selected,
		approvedAttemptId,
		vm,
		last
	}: {
		view: SceneView;
		selected: boolean;
		approvedAttemptId: string | null;
		vm: StoryboardVm;
		last: boolean;
	} = $props();

	const imageUrl = $derived(
		view.scene.image_path ? convertFileSrc(view.scene.image_path) : null
	);
	const duration = $derived(
		view.durationMs !== null ? `${(view.durationMs / 1000).toFixed(1)}s` : '—'
	);
</script>

<div
	class="card"
	class:selected
	role="button"
	tabindex="0"
	aria-label={`Scene ${view.scene.scene_id}`}
	onclick={() => vm.selectScene(view.scene.scene_id)}
	onpointerdown={(e) => e.stopPropagation()}
	onkeydown={(e) => e.key === 'Enter' && vm.selectScene(view.scene.scene_id)}
>
	<div class="lock" title="Scene order is script-locked. Reorder in Script.">
		<Icon name="lock" size={14} />
	</div>
	<span class="scene-id mono">{view.scene.scene_id}</span>

	<div class="thumb">
		{#if imageUrl}
			<img
				src={imageUrl}
				alt={`Scene ${view.scene.scene_id}`}
				loading="lazy"
			onerror={(e) => {
				const img = e.currentTarget as HTMLImageElement;
				img.style.display = 'none';
				img.nextElementSibling?.classList.remove('hidden');
			}}
			/>
		{/if}
		<div class="ph hidden" class:active={!imageUrl}>
			<Icon name="film" size={20} />
			<span class="mono">9:16</span>
		</div>
		{#if approvedAttemptId}
			<span class="approve"><Icon name="check" size={16} /></span>
		{/if}
	</div>

	<CandidateStrip
		candidates={view.candidates}
		approvedAttemptId={approvedAttemptId}
		onapprove={(attemptId) => vm.approve(view.scene.scene_id, attemptId)}
	/>

	<div class="chips mono">
		<span class="chip" title={`camera · ${view.camera}`}>{view.camera}</span>
		<span class="chip" title={`lighting · ${view.lighting}`}>{view.lighting}</span>
		<span class="chip duration" title={`duration · ${duration}`}>{duration}</span>
	</div>
	<div class="meta mono">
		<span class="subject" title={view.subject}>{view.subject}</span>
		<span class="transition" title={`transition to next · ${view.transition}`}>
			{view.transition}
		</span>
	</div>
	{#if !last}
		<span class="arrow"><Icon name="chevron-right" size={16} /></span>
	{/if}
</div>

<style>
	.card {
		position: relative;
		width: 200px;
		padding: 10px 10px 8px;
		border: 1px solid var(--border-default);
		border-radius: var(--radius-md);
		background: var(--surface-1);
		cursor: pointer;
		transition:
			border-color var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast) var(--ease-out);
	}
	.card:hover {
		border-color: var(--border-strong);
	}
	.card.selected {
		border-color: var(--accent);
		box-shadow: 0 0 0 1px var(--accent);
	}
	.lock {
		position: absolute;
		top: 8px;
		left: 8px;
		z-index: 2;
		color: var(--text-tertiary);
		opacity: 0.55;
		cursor: help;
	}
	.scene-id {
		position: absolute;
		top: 9px;
		right: 10px;
		font-size: 11px;
		color: var(--text-secondary);
	}
	.thumb {
		position: relative;
		width: 64px;
		height: 112px;
		margin: 14px auto 8px;
		border-radius: 4px;
		background: var(--surface-3);
		overflow: hidden;
		border: 1px solid var(--border-subtle);
	}
	.thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.ph {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		gap: 6px;
		align-items: center;
		justify-content: center;
		color: var(--text-tertiary);
		font-size: 9px;
	}
	.ph.hidden {
		display: none;
	}
	.ph.active {
		display: flex;
	}
	.approve {
		position: absolute;
		top: -6px;
		right: -6px;
		width: 22px;
		height: 22px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		background: var(--surface-0);
		border: 2px solid var(--status-ok);
		color: var(--status-ok);
	}
	.chips {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
		margin-top: 8px;
	}
	.chip {
		font-size: 11px;
		color: var(--text-secondary);
		background: var(--surface-2);
		border: 1px solid var(--border-subtle);
		border-radius: 3px;
		padding: 1px 5px;
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.chip.duration {
		color: var(--accent);
		font-variant-numeric: tabular-nums;
	}
	.meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
		margin-top: 6px;
		font-size: 10px;
		color: var(--text-tertiary);
	}
	.subject {
		max-width: 130px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.transition {
		white-space: nowrap;
	}
	.arrow {
		position: absolute;
		top: 50%;
		right: -17px;
		transform: translateY(-50%);
		color: var(--border-strong);
		pointer-events: none;
	}
</style>

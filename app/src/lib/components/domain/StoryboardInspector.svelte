<script lang="ts">
	/**
	 * StoryboardInspector — scene properties (UX §11): thumbnail, prompt /
	 * negative prompt, camera/lighting/composition/motion plan, workflow
	 * summary, QA placeholder when unavailable. Pictogram presets are
	 * read-only preview overrides (never persisted).
	 */
	import { convertFileSrc } from '@tauri-apps/api/core';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import PictogramPicker from '$lib/components/domain/PictogramPicker.svelte';
	import type { SceneView } from '$lib/stores/storyboard.store';
	import type { BackendWorkflow } from '$lib/models/workflow';

	let {
		view,
		workflow
	}: {
		view: SceneView;
		workflow: BackendWorkflow | null;
	} = $props();

	const imageUrl = $derived(view.scene.image_path ? convertFileSrc(view.scene.image_path) : null);
	const qa = $derived.by(() => {
		const attempts = view.candidates;
		if (attempts.length === 0) return null;
		const last = attempts[attempts.length - 1];
		if (!last) return null;
		return last.qaScore !== null ? { score: last.qaScore, passed: last.passed } : null;
	});

	function fmt(ms: number | null): string {
		if (ms === null) return '—';
		return `${(ms / 1000).toFixed(1)}s`;
	}
</script>

{#key view.scene.scene_id}
	<div class="inspector">
		<div class="thumb">
			{#if imageUrl}
				<img
					src={imageUrl}
					alt={`Scene ${view.scene.scene_id}`}
				onerror={(e) => {
					(e.currentTarget as HTMLImageElement).style.display = 'none';
				}}
				/>
			{:else}
				<div class="ph">
					<Icon name="film" size={22} />
					<span class="mono">thumbnail pending</span>
				</div>
			{/if}
			{#if qa}
				<span class="qa mono" class:passed={qa.passed} class:failed={!qa.passed}>
					QA {qa.score} · {qa.passed ? 'passed' : 'below threshold'}
				</span>
			{:else}
				<span class="qa mono placeholder">QA — placeholder (report unavailable)</span>
			{/if}
		</div>

		<section class="block">
			<h4 class="label">PLAN</h4>
			<dl class="rows mono">
				<div><dt>duration</dt><dd>{fmt(view.durationMs)}</dd></div>
				<div><dt>subject</dt><dd title={view.subject}>{view.subject}</dd></div>
				<div><dt>material</dt><dd title={view.material}>{view.material}</dd></div>
				<div><dt>objective</dt><dd title={view.objective}>{view.objective}</dd></div>
				<div><dt>camera</dt><dd title={view.camera}>{view.camera}</dd></div>
				<div><dt>lighting</dt><dd title={view.lighting}>{view.lighting}</dd></div>
				<div><dt>composition</dt><dd title={view.composition}>{view.composition}</dd></div>
				<div><dt>motion</dt><dd title={view.motion}>{view.motion}</dd></div>
				<div><dt>transition</dt><dd title={view.transition}>{view.transition}</dd></div>
			</dl>
		</section>

		<section class="block">
			<h4 class="label">PROMPT</h4>
			{#if view.prompt}
				<p class="text">{view.prompt}</p>
			{:else}
				<p class="text muted">No compiled prompt yet — run the episode to generate one.</p>
			{/if}
			{#if view.negativePrompt}
				<h5 class="label">NEGATIVE</h5>
				<p class="text muted">{view.negativePrompt}</p>
			{/if}
		</section>

		{#if workflow}
			<section class="block">
				<h4 class="label">WORKFLOW</h4>
				<dl class="rows mono">
					<div><dt>profile</dt><dd>{workflow.profile ?? '—'}</dd></div>
					<div><dt>sampler</dt><dd>{workflow.sampler ?? '—'}</dd></div>
					<div><dt>steps / cfg</dt>
						<dd>{workflow.steps ?? '—'} / {workflow.cfg ?? '—'}</dd>
					</div>
					<div><dt>resolution</dt><dd>{String(workflow.resolution ?? '—')}</dd></div>
				</dl>
			</section>
		{/if}

		<section class="block">
			<h4 class="label">DIRECTION — PREVIEW ONLY</h4>
			<PictogramPicker
				values={{
					camera: view.camera,
					lighting: view.lighting,
					composition: view.composition
				}}
				label={`Scene ${view.scene.scene_id}`}
			/>
			<p class="hint mono">the run uses KB values · reorder in Script</p>
		</section>
	</div>
{/key}

<style>
	.inspector {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
		padding: var(--space-4);
		overflow-y: auto;
	}
	.thumb {
		position: relative;
		align-self: center;
		width: 96px;
		height: 168px;
		border-radius: 6px;
		border: 1px solid var(--border-subtle);
		background: var(--surface-3);
		overflow: hidden;
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
		gap: 8px;
		align-items: center;
		justify-content: center;
		color: var(--text-tertiary);
		font-size: 10px;
	}
	.qa {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		padding: 3px 6px;
		font-size: 9.5px;
		text-align: center;
		background: var(--surface-0);
		border-top: 1px solid var(--border-subtle);
	}
	.qa.passed {
		color: var(--status-ok);
	}
	.qa.failed {
		color: var(--status-error);
	}
	.qa.placeholder {
		color: var(--text-tertiary);
	}
	.block {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.block h4,
	.block h5 {
		margin: 0;
	}
	.rows {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
	}
	.rows div {
		display: flex;
		justify-content: space-between;
		gap: 10px;
	}
	.rows dt {
		color: var(--text-tertiary);
		font-size: 10.5px;
		white-space: nowrap;
	}
	.rows dd {
		margin: 0;
		color: var(--text-primary);
		font-size: 10.5px;
		text-align: right;
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.text {
		margin: 0;
		font: var(--body-sm);
		color: var(--text-primary);
		line-height: 1.5;
		max-height: 160px;
		overflow-y: auto;
		word-break: break-word;
	}
	.text.muted {
		color: var(--text-tertiary);
	}
	.hint {
		margin: 0;
		font-size: 9.5px;
		color: var(--text-tertiary);
	}
</style>

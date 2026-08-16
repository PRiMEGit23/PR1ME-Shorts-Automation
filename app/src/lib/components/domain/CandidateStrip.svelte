<script lang="ts">
	/**
	 * CandidateStrip — render history attempts as a thumbnail row (VDS §14:
	 * 4 thumbs 44×78, scrollable if > 4, approved = status-ok border + ✓).
	 * Approval here is a preview-only override (UX §11 — product layer).
	 */
	import { convertFileSrc } from '@tauri-apps/api/core';
	import Icon from '$lib/components/primitives/Icon.svelte';
	import type { CandidateView } from '$lib/stores/storyboard.store';

	let {
		candidates,
		approvedAttemptId,
		onapprove
	}: {
		candidates: CandidateView[];
		approvedAttemptId: string | null;
		onapprove: (attemptId: string | null) => void;
	} = $props();
</script>

{#if candidates.length > 0}
	<div class="strip" role="listbox" aria-label="Render candidates">
		{#each candidates as candidate (candidate.attemptId)}
			<button
				class="thumb"
				class:approved={candidate.attemptId === approvedAttemptId}
				class:passed={candidate.passed}
				class:failed={candidate.status === 'failed'}
				title={`attempt ${candidate.index} · seed ${candidate.seed}${candidate.passed ? ' · QA passed' : ''}`}
				role="option"
				aria-selected={candidate.attemptId === approvedAttemptId}
				onclick={() =>
					onapprove(
						candidate.attemptId === approvedAttemptId ? null : candidate.attemptId
					)}
			>
				{#if candidate.imagePath}
					<img
						src={convertFileSrc(candidate.imagePath)}
						alt={`attempt ${candidate.index}`}
						loading="lazy"
						onerror={(e) => {
							(e.currentTarget as HTMLImageElement).style.display = 'none';
						}}
					/>
				{:else}
					<span class="ph mono">{candidate.index + 1}</span>
				{/if}
				{#if candidate.passed}
					<span class="ok" title="QA passed"><Icon name="check" size={11} /></span>
				{/if}
				{#if candidate.qaScore !== null}
					<span class="score mono">{Math.round(candidate.qaScore)}</span>
				{/if}
			</button>
		{/each}
	</div>
{:else}
	<div class="none mono">no candidates yet</div>
{/if}

<style>
	.strip {
		display: flex;
		gap: 6px;
		overflow-x: auto;
		padding: 6px 8px;
		scrollbar-width: none;
	}
	.thumb {
		position: relative;
		width: 44px;
		height: 78px;
		flex-shrink: 0;
		padding: 0;
		border: 1px solid var(--border-default);
		border-radius: 3px;
		background: var(--surface-3);
		overflow: hidden;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: border-color var(--dur-fast) var(--ease-out);
	}
	.thumb:hover {
		border-color: var(--border-strong);
	}
	.thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.thumb .ph {
		font-size: 12px;
		color: var(--text-tertiary);
	}
	.thumb.approved {
		border: 2px solid var(--status-ok);
	}
	.thumb.failed {
		opacity: 0.55;
	}
	.thumb .ok {
		position: absolute;
		top: 2px;
		right: 2px;
		width: 16px;
		height: 16px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 8px;
		background: var(--surface-0);
		color: var(--status-ok);
	}
	.thumb .score {
		position: absolute;
		bottom: 2px;
		right: 3px;
		font-size: 9px;
		color: var(--text-tertiary);
		background: var(--surface-0);
		border-radius: 2px;
		padding: 0 2px;
	}
	.none {
		font-size: 10px;
		color: var(--text-tertiary);
		padding: 8px;
	}
</style>

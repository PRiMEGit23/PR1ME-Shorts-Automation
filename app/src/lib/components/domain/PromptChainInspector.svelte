<script lang="ts">
	/**
	 * PromptChainInspector — per-scene prompt chain (2S4 Workflow): the
	 * Subject → Material → Lighting → Camera → Composition → Rendering →
	 * Negative Prompt chain with collapsible sections. Values come from the
	 * KB scene plan / prompt pack join (honest gaps show "—").
	 */
	import type { SceneView } from '$lib/stores/storyboard.store';

	let { view }: { view: SceneView } = $props();

	const sections = $derived([
		{ id: 'subject', label: 'Subject', value: view.subject },
		{ id: 'material', label: 'Material', value: view.material },
		{ id: 'lighting', label: 'Lighting', value: view.lighting },
		{ id: 'camera', label: 'Camera', value: [view.camera, view.plan?.lens].filter(Boolean).join(' · ') || '—' },
		{ id: 'composition', label: 'Composition', value: view.composition },
		{ id: 'rendering', label: 'Rendering', value: view.rendering },
		{ id: 'negative', label: 'Negative Prompt', value: view.negativePrompt || '—' }
	]);

	const open = $state<Record<string, boolean>>({ subject: true });

	function toggle(sectionId: string, isOpen: boolean) {
		open[sectionId] = isOpen;
	}
</script>

{#key view.scene.scene_id}
	<div class="chain-inspector">
		{#each sections as section (section.id)}
			<details open={!!open[section.id]} class="section"
				ontoggle={(e) => toggle(section.id, e.currentTarget.open)}
			>
				<summary class="head">
					<span class="label">{section.label}</span>
					{#if section.id === 'camera'}
						<span class="tag mono">lens</span>
					{/if}
				</summary>
				<p class="value">{section.value}</p>
			</details>
		{/each}
		{#if !view.plan}
			<p class="note mono">scene plan not found in the knowledge base — run generates these</p>
		{/if}
	</div>
{/key}

<style>
	.chain-inspector {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.section {
		border: 1px solid var(--border-default);
		border-radius: var(--radius-sm);
		background: var(--surface-1);
	}
	.section[open] {
		border-color: var(--border-strong);
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 8px 10px;
		cursor: pointer;
		list-style: none;
		font-size: 11.5px;
		font-weight: 600;
		color: var(--text-secondary);
		user-select: none;
	}
	.head::-webkit-details-marker {
		display: none;
	}
	.head::before {
		content: '▸';
		font-size: 9px;
		color: var(--text-tertiary);
		transition: transform var(--dur-fast) var(--ease-out);
	}
	.section[open] .head::before {
		transform: rotate(90deg);
	}
	.tag {
		font-size: 9px;
		font-weight: 400;
		color: var(--text-tertiary);
	}
	.value {
		margin: 0;
		padding: 0 10px 10px;
		font: var(--body-sm);
		color: var(--text-primary);
		line-height: 1.5;
		word-break: break-word;
		max-height: 140px;
		overflow-y: auto;
	}
	.note {
		margin: 0;
		font-size: 9.5px;
		color: var(--text-tertiary);
	}
</style>

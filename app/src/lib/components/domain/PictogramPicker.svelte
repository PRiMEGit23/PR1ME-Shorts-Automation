<script lang="ts">
	/**
	 * PictogramPicker — product-owned static SVG preset grids (UX §11):
	 * camera / lighting / composition presets rendered as engineering-line
	 * glyphs. Highlighting tracks the KB value; a click is a read-only
	 * override for preview only — the run always uses the KB values.
	 */
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';

	type Preset = { id: string; label: string; paths: string[] };

	const CAMERA_PRESETS: Preset[] = [
		{
			id: 'push-in',
			label: 'push-in',
			paths: ['M10 15V8', 'M10 8l-3 3', 'M10 8l3 3', 'M4 4.5h12', 'M4 4.5V3M16 4.5V3', 'M4 6v2M16 6v2']
		},
		{
			id: 'orbit',
			label: 'orbit',
			paths: ['M10 10m-5 0a5 5 0 1 0 10 0a5 5 0 1 0-10 0', 'M10 10l5.5-2', 'M15.5 8l.8 2.8', 'M3.5 3.5h3.5', 'M3.5 3.5V7']
		},
		{
			id: 'dolly',
			label: 'dolly',
			paths: ['M6 14v2.5', 'M14 14v2.5', 'M6 17h8', 'M3 10h14', 'M13 7.5l4 2.5-4 2.5', 'M3.5 10H3']
		},
		{
			id: 'tilt',
			label: 'tilt',
			paths: ['M10 4v9', 'M10 13l-3-3', 'M10 13l3-3', 'M4 16.5h12', 'M16 15v3', 'M4 15v3']
		},
		{
			id: 'crane',
			label: 'crane',
			paths: ['M10 17V7', 'M10 7L7 10', 'M10 7l3 3', 'M3.5 4h13', 'M14 4v2', 'M16.5 4l-2.5 2']
		},
		{
			id: 'thumb',
			label: 'thumb',
			paths: ['M3.5 5h13v10h-13z', 'M3.5 8.5h13', 'M6 11.5h3.5', 'M12.5 12.5h1']
		}
	];

	const LIGHT_PRESETS: Preset[] = [
		{
			id: 'rim',
			label: 'rim',
			paths: ['M10 3.5v3', 'M4.5 10h3', 'M7 5.5l1.5 1.5', 'M10 14a4 4 0 0 1 0-8', 'M5.5 5.5l2 2']
		},
		{
			id: 'soft',
			label: 'soft',
			paths: ['M10 10m-5.5 0a5.5 5.5 0 1 0 11 0a5.5 5.5 0 1 0-11 0', 'M10 6.5a3.5 3.5 0 0 1 0 7']
		},
		{
			id: 'back',
			label: 'back',
			paths: ['M3.5 10h13', 'M12 7l4 3-4 3', 'M10 5v3', 'M10 12v3']
		},
		{
			id: 'key',
			label: 'key',
			paths: ['M17 10H4', 'M8 7l-4 3 4 3', 'M12 4.5v11']
		},
		{
			id: 'fill',
			label: 'fill',
			paths: ['M3.5 10h13', 'M12 7l4 3-4 3', 'M10 4v3', 'M10 13v3']
		},
		{
			id: 'practical',
			label: 'practical',
			paths: ['M9 10a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0', 'M10 3.5v2.5', 'M10 14v2.5', 'M3.5 10H6', 'M14 10h2.5', 'M5.5 5.5l2 2', 'M14.5 5.5l-2 2', 'M5.5 14.5l2-2', 'M14.5 14.5l-2-2']
		}
	];

	const COMP_PRESETS: Preset[] = [
		{
			id: 'center',
			label: 'center',
			paths: ['M3.5 3.5h13v13h-13z', 'M10 7v6', 'M7 10h6']
		},
		{
			id: 'thirds',
			label: 'thirds',
			paths: ['M3.5 3.5h13v13h-13z', 'M10 3.5v13', 'M3.5 10h13']
		},
		{
			id: 'leading',
			label: 'leading-lines',
			paths: ['M3.5 3.5h13v13h-13z', 'M3.5 16.5L16.5 3.5', 'M8 16.5L16.5 8', 'M12.5 16.5l4-4']
		},
		{
			id: 'frame',
			label: 'frame',
			paths: ['M3.5 3.5h13v13h-13z', 'M6 6h8v8H6z', 'M6 6h8M14 14H6']
		},
		{
			id: 'low',
			label: 'low-angle',
			paths: ['M3.5 13.5h13', 'M5.5 16.5h9', 'M10 4.5l-4 9h8z']
		},
		{
			id: 'high',
			label: 'high-angle',
			paths: ['M3.5 6.5h13', 'M5.5 3.5h9', 'M10 15.5l-4-9h8z']
		}
	];

	const GROUPS: { label: string; presets: Preset[] }[] = [
		{ label: 'Camera', presets: CAMERA_PRESETS },
		{ label: 'Lighting', presets: LIGHT_PRESETS },
		{ label: 'Composition', presets: COMP_PRESETS }
	];

	let {
		values,
		label
	}: {
		values: { camera: string; lighting: string; composition: string };
		label: string;
	} = $props();

	let overrides: Record<string, string> = $state({});

	function matches(value: string, presetId: string): boolean {
		return value.toLowerCase().includes(presetId.replace('-', ' ')) ||
			value.toLowerCase().includes(presetId);
	}

	function pick(group: string, presetId: string): void {
		if (overrides[group] === presetId) {
			overrides = { ...overrides, [group]: '' };
		} else {
			overrides = { ...overrides, [group]: presetId };
		}
	}
</script>

<div class="picker" role="group" aria-label={`${label} pictogram pickers`}>
	{#each GROUPS as group (group.label)}
		<div class="group">
			<span class="g-label label">{group.label}</span>
			<div class="presets">
				{#each group.presets as preset (preset.id)}
					<Tooltip label={`${preset.label}${overrides[group.label] === preset.id ? ' · preview override' : ''}`}>
						<button
							class="preset"
							class:active={matches(
								group.label === 'Camera'
									? values.camera
									: group.label === 'Lighting'
										? values.lighting
										: values.composition,
								preset.id
							)}
							class:override={overrides[group.label] === preset.id}
							onclick={() => pick(group.label, preset.id)}
							aria-pressed={overrides[group.label] === preset.id}
						>
							<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4"
								stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								{#each preset.paths as d (d)}
									<path {d} />
								{/each}
							</svg>
						</button>
					</Tooltip>
				{/each}
			</div>
		</div>
	{/each}
	{#if Object.values(overrides).some(Boolean)}
		<p class="note mono">preview-only — the run always uses KB values</p>
	{/if}
</div>

<style>
	.picker {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
	.group {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.g-label {
		font-size: 10px;
		color: var(--text-tertiary);
	}
	.presets {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.preset {
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--border-default);
		border-radius: var(--radius-sm);
		background: var(--surface-1);
		color: var(--text-tertiary);
		cursor: pointer;
	}
	.preset:hover {
		border-color: var(--border-strong);
		color: var(--text-primary);
	}
	.preset.active {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}
	.preset.override {
		border-color: var(--status-info);
		color: var(--status-info);
		background: var(--status-info-soft);
	}
	.note {
		font-size: 10px;
		color: var(--text-tertiary);
	}
</style>

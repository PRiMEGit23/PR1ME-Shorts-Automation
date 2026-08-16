<script lang="ts">
	/**
	 * Icon — single stroke set, 1.5 px stroke, round caps/joins, 24 grid
	 * (VISUAL_DESIGN_SYSTEM §27). No fills (exception: state checks/dots).
	 */
	import type { SVGAttributes } from 'svelte/elements';

	type IconName = keyof typeof PATHS;

	let {
		name,
		size = 16,
		strokeWidth = 1.5,
		...rest
	}: SVGAttributes<SVGSVGElement> & {
		name: IconName;
		size?: number;
		strokeWidth?: number;
	} = $props();

	const paths = $derived(PATHS[name] ?? PATHS.info);
</script>

<svg
	{...rest}
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width={strokeWidth}
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#each paths as d (d)}
		<path {d} />
	{/each}
</svg>

<style>
	svg {
		display: block;
		flex-shrink: 0;
	}
</style>

<script lang="ts" module>
	export type IconName = keyof typeof PATHS;

	export const PATHS = {
		/* workbench glyphs (VDS §27, locked) */
		library: ['M3.5 3.5h7v7h-7z', 'M13.5 3.5h7v7h-7z', 'M3.5 13.5h7v7h-7z', 'M13.5 13.5h7v7h-7z'],
		script: ['M14.5 3.5l6 6L7.5 22.5h-6v-6L14.5 3.5z'],
		storyboard: [
			'M3.5 4.5h17v15h-17z',
			'M3.5 8h2M3.5 12h2M3.5 16h2',
			'M18.5 8h2M18.5 12h2M18.5 16h2'
		],
		workflow: [
			'M12 6.5l5.7 5.5M17.7 12l-5.7 5.5M12 17.5L6.3 12M6.3 12L12 6.5',
			'M5 12m-1.8 0a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0-3.6 0',
			'M12 5m-1.8 0a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0-3.6 0',
			'M19 12m-1.8 0a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0-3.6 0',
			'M12 19m-1.8 0a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0-3.6 0'
		],
		render: ['M8.5 5.5l11 6.5-11 6.5z'],
		edit: ['M6 6m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0', 'M6 18m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0', 'M8.5 8L20 19.5', 'M8.5 16L20 4.5'],
		deliver: ['M12 4.5v11', 'M7.5 10L12 5.5 16.5 10', 'M5 19.5h14'],
		insights: ['M3.5 16.5l5-5.5 3.5 3 7-8', 'M14.5 6h5v5'],

		/* panel toggles */
		explorer: ['M3.5 5h6v5h-6z', 'M3.5 14h6v5h-6z', 'M12.5 7.5h8', 'M12.5 16.5h8'],
		assets: [
			'M3.5 5.5h17v13h-17z',
			'M9.5 10m-1.5 0a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0',
			'M20.5 18.5l-5.5-5.5-3.5 3.5-3.5-3.5L3.5 18.5'
		],
		inspector: ['M12 12m-8.5 0a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0', 'M12 8h.01', 'M12 11.5v5'],
		timeline: [
			'M3.5 6.5h17v6h-17z',
			'M6.5 9.5v3M10.5 9.5v3M14.5 9.5v3M18.5 9.5v3',
			'M21 12v7'
		],
		terminal: ['M3.5 5h17v14h-17z', 'M7.5 9.5l3 2.5-3 2.5', 'M12.5 14.5h4'],

		/* chrome */
		aperture: ['M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0', 'M12 3.5l5.2 9L12 20.5l-5.2-8.9z'],
		search: ['M11 11m-6.5 0a6.5 6.5 0 1 0 13 0a6.5 6.5 0 1 0-13 0', 'M16 16l4.5 4.5'],
		'chevron-down': ['M6 9.5l6 6 6-6'],
		'chevron-right': ['M9.5 6l6 6-6 6'],
		'chevron-up': ['M6 14.5l6-6 6 6'],
		'chevron-left': ['M14.5 6l-6 6 6 6'],
		plus: ['M12 5.5v13', 'M5.5 12h13'],
		close: ['M6 6l12 12', 'M18 6L6 18'],
		check: ['M5 13l4 4L19 7'],
		pin: ['M9.5 4.5h5l-1 5.5 3.5 3.5H7l3.5-3.5-1-5.5z', 'M12 15.5v4'],
		detach: ['M3.5 4.5h11v11h-11z', 'M17.5 3.5h3v3', 'M20.5 3.5L13.5 10.5'],
		menu: ['M12 6.5h.01', 'M12 12h.01', 'M12 17.5h.01'],
		minimize: ['M5 12.5h14'],
		maximize: ['M5.5 5.5h13v13h-13z'],
		restore: ['M5.5 5.5h10v10h-10z', 'M8.5 8.5h10v10h-10z'],
		generate: ['M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0', 'M12 8.5v7', 'M8.5 12h7'],
		connections: [
			'M9 3v3.5M15 3v3.5',
			'M7.5 6.5h9',
			'M10.5 9.5v2.5a1.5 1.5 0 0 0 3 0v-2.5',
			'M12 12v4.5'
		],
		preferences: [
			'M12 12m-3.2 0a3.2 3.2 0 1 0 6.4 0a3.2 3.2 0 1 0-6.4 0',
			'M12 4.5v2M12 17.5v2M4.5 12h2M17.5 12h2',
			'M6.7 6.7l1.4 1.4M15.9 15.9l1.4 1.4M17.3 6.7l-1.4 1.4M8.1 15.9l-1.4 1.4'
		],
		refresh: ['M20 12a8 8 0 1 1-2.34-5.66', 'M20.5 3.5v4.5h-4.5'],
		lock: ['M5.5 10.5h13v9h-13z', 'M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5'],
		queue: ['M3.5 4.5h17v15h-17z', 'M3.5 10.5h17'],
		clock: ['M12 12m-8.5 0a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0', 'M12 7.5V12l3 2'],
		doc: ['M6.5 3.5h7l4 4v13h-11z', 'M13.5 3.5v4h4'],
		play: ['M8.5 5.5l11 6.5-11 6.5z'],
		pause: ['M8.5 5.5h3v13h-3z', 'M13.5 5.5h3v13h-3z'],
		stop: ['M7 7h10v10H7z'],
		info: ['M12 12m-8.5 0a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0', 'M12 8h.01', 'M12 11.5v5'],

		/* knowledge / data (2S3) */
		grid: ['M3.5 3.5h7v7h-7z', 'M13.5 3.5h7v7h-7z', 'M3.5 13.5h7v7h-7z', 'M13.5 13.5h7v7h-7z'],
		table: [
			'M3.5 5h17v14h-17z',
			'M3.5 9.5h17M3.5 14.5h17',
			'M9.5 5v14M15.5 5v14'
		],
		import: ['M12 4v9', 'M8 9.5l4 4 4-4', 'M5 19.5h14'],
		export: ['M12 15V6', 'M8 10.5l4-4 4 4', 'M5 19.5h14'],
		trash: ['M5 6.5h14', 'M9 6.5V4.5h6v2', 'M6.5 6.5l1 13h9l1-13', 'M10 10v6M14 10v6'],
		duplicate: [
			'M4.5 8.5H4a1.5 1.5 0 0 1 1.5-1.5V8.5z',
			'M5.5 5.5H18A1.5 1.5 0 0 1 19.5 7v13a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 20V7',
			'M9.5 12h4M9.5 16h2.5'
		],
		warning: ['M12 4.5l9 15.5H3l9-15.5z', 'M12 9.5v4', 'M12 16.5h.01'],
		columns: ['M3.5 5h17v14h-17z', 'M12 5v14'],
		magic: ['M4.5 19.5L14.5 9.5', 'M15.5 5.5l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z'],
		dot: ['M12 12m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0']
	} satisfies Record<string, string[]>;
</script>
<script lang="ts">
	/**
	 * ApertureMark — the PR1ME logo mark (VDS §1): a 5-blade ring enclosing
	 * the numeral 1, rendered as a single stroke glyph. Sizes 20/24/32/48.
	 * Never recolored: PRIME Blue on surface-0 (or surface-0 on accent in
	 * brand moments).
	 */
	let { size = 24, color = 'var(--accent)' }: { size?: number; color?: string } = $props();
</script>

<svg
	class="aperture"
	width={size}
	height={size}
	viewBox="0 0 48 48"
	fill="none"
	stroke={color}
	stroke-width="2"
	stroke-linecap="round"
	aria-hidden="true"
>
	<circle cx="24" cy="24" r="19" />
	<line x1="24" y1="3" x2="24" y2="8" />
	<line x1="42.9" y1="17.8" x2="39.4" y2="20.7" />
	<line x1="35.7" y1="40.2" x2="33.4" y2="36.4" />
	<line x1="12.3" y1="40.2" x2="14.6" y2="36.4" />
	<line x1="5.1" y1="17.8" x2="8.6" y2="20.7" />
	<text
		x="24"
		y="31.5"
		text-anchor="middle"
		font-family="var(--font-ui)"
		font-size="26"
		font-weight="600"
		fill={color}
		stroke="none"
	>1</text>
</svg>
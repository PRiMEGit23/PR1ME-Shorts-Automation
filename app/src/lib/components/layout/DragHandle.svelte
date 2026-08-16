<script lang="ts">
	/**
	 * DragHandle — 4px zone resize handle (VDS §9: 4px grid + accent hover).
	 * Double-click toggles zone collapse (§39).
	 */
	let {
		orientation = 'vertical',
		ondrag,
		ondblclick
	}: {
		orientation?: 'vertical' | 'horizontal';
		ondrag: (delta: number) => void;
		ondblclick?: () => void;
	} = $props();

	let active = $state(false);
	let last = $state(0);

	function onpointerdown(e: PointerEvent) {
		active = true;
		last = orientation === 'vertical' ? e.clientX : e.clientY;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		e.preventDefault();
	}
	function onpointermove(e: PointerEvent) {
		if (!active) return;
		const now = orientation === 'vertical' ? e.clientX : e.clientY;
		ondrag(now - last);
		last = now;
	}
	function onpointerup() {
		active = false;
	}
</script>

<div
	class="handle"
	class:active
	class:horizontal={orientation === 'horizontal'}
	role="separator"
	aria-orientation={orientation}
	onpointerdown={onpointerdown}
	onpointermove={onpointermove}
	onpointerup={onpointerup}
	onpointercancel={onpointerup}
	ondblclick={ondblclick}
></div>

<style>
	.handle {
		position: relative;
		flex-shrink: 0;
		z-index: 3;
		cursor: col-resize;
		touch-action: none;
	}
	.handle::after {
		content: '';
		position: absolute;
		inset: 0;
		background: var(--accent);
		opacity: 0;
		transition: opacity var(--motion-fast) var(--ease-out);
	}
	.handle:hover::after,
	.handle.active::after {
		opacity: 1;
	}
	.handle:not(.horizontal) {
		width: 4px;
		margin: 0 -2px;
	}
	.handle.horizontal {
		height: 4px;
		margin: -2px 0;
		cursor: row-resize;
	}
</style>
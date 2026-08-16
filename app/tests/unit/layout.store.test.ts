/**
 * layout service/store — presets (UX_ARCHITECTURE §18) + zone behavior.
 */

import { describe, expect, it } from 'vitest';
import { DEFAULT_LAYOUTS } from '$lib/services/layout.service';
import { LayoutStore } from '$lib/stores/layout.store';

describe('DEFAULT_LAYOUTS', () => {
	it('defines all 8 workbenches', () => {
		expect(Object.keys(DEFAULT_LAYOUTS)).toHaveLength(8);
	});

	it('script = left explorer + right inspector + bottom timeline (UX §18)', () => {
		const s = DEFAULT_LAYOUTS.script;
		expect(s.zones.left).toEqual(['explorer']);
		expect(s.zones.right).toEqual(['inspector']);
		expect(s.zones.bottom).toEqual(['timeline']);
		expect(s.collapsed).toEqual({ left: false, right: false, bottom: false });
	});

	it('library collapses right and bottom docks', () => {
		const l = DEFAULT_LAYOUTS.library;
		expect(l.collapsed.right).toBe(true);
		expect(l.collapsed.bottom).toBe(true);
	});

	it('edit has no bottom zone; insights has no right zone', () => {
		expect(DEFAULT_LAYOUTS.edit.zones.bottom).toEqual([]);
		expect(DEFAULT_LAYOUTS.insights.zones.right).toEqual([]);
	});
});

describe('LayoutStore', () => {
	it('presets are deep-cloned per workbench', () => {
		const s = new LayoutStore();
		s.states.script.zones.left = [];
		expect(DEFAULT_LAYOUTS.script.zones.left).toEqual(['explorer']);
		expect(s.states.library.zones.left).toEqual(['explorer']);
	});

	it('togglePanel shows/hides in the default zone', () => {
		const s = new LayoutStore();
		s.setWorkbench('library');
		expect(s.isPanelVisible('terminal')).toBe(false);
		s.togglePanel('terminal');
		expect(s.isPanelVisible('terminal')).toBe(true);
		expect(s.current().zones.bottom).toContain('terminal');
		s.togglePanel('terminal');
		expect(s.isPanelVisible('terminal')).toBe(false);
	});

	it('clamps zone sizes to the documented ranges', () => {
		const s = new LayoutStore();
		s.setZoneSize('left', 10);
		expect(s.current().sizes.left).toBe(200);
		s.setZoneSize('left', 900);
		expect(s.current().sizes.left).toBe(480);
		s.setZoneSize('bottom', 250);
		expect(s.current().sizes.bottom).toBe(250);
	});

	it('pin auto-hides to the edge strip; re-pin restores (VDS §39)', () => {
		const s = new LayoutStore();
		s.setWorkbench('script');
		s.pin('inspector', false);
		expect(s.current().zones.right).not.toContain('inspector');
		expect(s.isPanelPinned('inspector')).toBe(false);
		s.pin('inspector', true);
		expect(s.current().zones.right).toContain('inspector');
	});

	it('reset restores the documented preset', () => {
		const s = new LayoutStore();
		s.setWorkbench('script');
		s.togglePanel('explorer');
		s.setZoneSize('left', 400);
		s.resetWorkbench('script');
		expect(s.current()).toEqual(DEFAULT_LAYOUTS.script);
	});
});
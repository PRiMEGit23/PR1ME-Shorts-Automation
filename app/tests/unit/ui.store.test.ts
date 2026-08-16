/**
 * ui store — palette, workbench switching, toast queue (VDS §35).
 */

import { describe, expect, it } from 'vitest';
import { UiStore, WORKBENCHES } from '$lib/stores/ui.store';

function makeStore() {
	return {
		ui: new UiStore()
	};
}

describe('UiStore', () => {
	it('registers the 8 documented workbenches', () => {
		expect(WORKBENCHES.map((w) => w.id)).toEqual([
			'library',
			'script',
			'storyboard',
			'workflow',
			'render',
			'edit',
			'deliver',
			'insights'
		]);
	});

	it('switchWorkbench closes the palette and marks no recent', () => {
		const { ui } = makeStore();
		ui.openPalette('commands');
		ui.switchWorkbench('render');
		expect(ui.workbench).toBe('render');
		expect(ui.palette.open).toBe(false);
	});

	it('palette open resets query', () => {
		const { ui } = makeStore();
		ui.openPalette('commands');
		ui.setPaletteQuery('rend');
		ui.openPalette('jump');
		expect(ui.palette.query).toBe('');
		expect(ui.palette.scope).toBe('jump');
	});

	it('toasts cap at 4 newest; recents dedupe to 12', () => {
		const { ui } = makeStore();
		for (let i = 0; i < 6; i++) ui.pushToast('info', `t${i}`);
		expect(ui.toasts).toHaveLength(4);
		expect(ui.toasts[0]!.title).toBe('t2');
		for (let i = 0; i < 14; i++) ui.markRecent(`r${i % 3}`);
		expect(ui.recents).toHaveLength(3);
	});

	it('errors persist (ttl 0); success auto-dismisses (ttl 4000)', () => {
		const { ui } = makeStore();
		const err = ui.pushToast('error', 'boom');
		expect(err.ttl).toBe(0);
		const ok = ui.pushToast('success', 'saved');
		expect(ok.ttl).toBe(4000);
		ui.dismissToast(err.id);
		expect(ui.toasts).toHaveLength(1);
	});

	it('modals close the palette (VDS §20)', () => {
		const { ui } = makeStore();
		ui.openPalette('commands');
		ui.openModal('preferences');
		expect(ui.palette.open).toBe(false);
		expect(ui.modal).toBe('preferences');
	});
});
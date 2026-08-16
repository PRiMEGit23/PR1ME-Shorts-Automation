/**
 * editor store — tabs, dirty state, undo/redo scaffolding, reopen.
 */

import { describe, expect, it } from 'vitest';
import { EditorStore } from '$lib/stores/editor.store';

describe('EditorStore', () => {
	it('opens, activates, closes, reopens (Cmd+Shift+T)', () => {
		const s = new EditorStore();
		const d1 = s.newScriptDocument();
		const d2 = s.newScriptDocument();
		s.open(d1);
		s.open(d2);
		expect(s.active()!.id).toBe(d2.id);
		s.close(d2.id);
		expect(s.active()!.id).toBe(d1.id);
		s.reopenLastClosed();
		expect(s.documents).toHaveLength(2);
	});

	it('new script document is an empty draft', () => {
		const s = new EditorStore();
		const d = s.newScriptDocument();
		expect(d.type).toBe('script');
		expect(d.topic).toBe('');
		expect(d.narration).toBe('');
		expect(d.difficulty).toBe('B');
		expect(d.dirty).toBe(false);
	});

	it('updateDocument marks dirty and snapshots once', () => {
		const s = new EditorStore();
		const d = s.newScriptDocument();
		s.open(d);
		s.updateDocument<typeof d>(d.id, { topic: 'Anglerfish' });
		expect(s.active()!.dirty).toBe(true);
		expect(s.undo[d.id]).toHaveLength(1);
		s.updateDocument<typeof d>(d.id, { narration: 'Hello' });
		expect(s.undo[d.id]).toHaveLength(1);
	});

	it('undo restores the pre-edit snapshot; redo re-applies', () => {
		const s = new EditorStore();
		const d = s.newScriptDocument();
		s.open(d);
		s.updateDocument<typeof d>(d.id, { topic: 'Anglerfish' });
		expect(s.undoDocument(d.id)).toBe(true);
		expect((s.active() as typeof d).topic).toBe('');
		expect(s.redoDocument(d.id)).toBe(true);
		expect((s.active() as typeof d).topic).toBe('Anglerfish');
	});

	it('undo with no history returns false', () => {
		const s = new EditorStore();
		expect(s.undoDocument('nope')).toBe(false);
	});
});
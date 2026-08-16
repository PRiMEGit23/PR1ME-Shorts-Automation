/**
 * fuzzy core — subsequence scoring (UX_ARCHITECTURE §8).
 */

import { describe, expect, it } from 'vitest';
import { fuzzyMatch, fuzzyRank } from '$lib/core/fuzzy';

describe('fuzzyMatch', () => {
	it('matches exact text with max score', () => {
		const m = fuzzyMatch('script', 'Script');
		expect(m).not.toBeNull();
		expect(m!.indices).toHaveLength(6);
	});

	it('matches subsequences', () => {
		const m = fuzzyMatch('scrt', 'Script');
		expect(m).not.toBeNull();
		expect(m!.score).toBeGreaterThan(0);
	});

	it('returns null for non-matches', () => {
		expect(fuzzyMatch('xyz', 'Script')).toBeNull();
		expect(fuzzyMatch('longer', 'ab')).toBeNull();
	});

	it('prefers word starts', () => {
		const wordStart = fuzzyMatch('ren', 'render board');
		const scattered = fuzzyMatch('ren', 'wrender');
		expect(wordStart).not.toBeNull();
		expect(scattered).not.toBeNull();
		expect(wordStart!.score).toBeGreaterThan(scattered!.score);
	});

	it('ranks contiguous runs higher', () => {
		const contiguous = fuzzyMatch('render', 'Render board');
		const gapped = fuzzyMatch('rned', 'Render board');
		expect(contiguous!.score).toBeGreaterThan(gapped!.score);
	});

	it('case-insensitive', () => {
		expect(fuzzyMatch('SCRIPT', 'script')).not.toBeNull();
	});

	it('empty query matches everything at score 0', () => {
		expect(fuzzyMatch('', 'anything')).toEqual({ score: 0, indices: [] });
	});
});

describe('fuzzyRank', () => {
	const pool = ['Library', 'Script', 'Storyboard', 'Workflow', 'Render', 'Edit', 'Deliver', 'Insights'];

	it('returns up to 20 results sorted by score', () => {
		const r = fuzzyRank('sc', pool, (s) => s);
		expect(r.length).toBeGreaterThan(0);
		expect(r[0]!.item).toBe('Script');
		for (let i = 1; i < r.length; i++) {
			expect(r[i - 1]!.match.score).toBeGreaterThanOrEqual(r[i]!.match.score);
		}
	});

	it('empty query returns the first 20 unchanged', () => {
		const r = fuzzyRank('', pool, (s) => s);
		expect(r.map((x) => x.item)).toEqual(pool.slice(0, 20));
	});

	it('excludes non-matching candidates', () => {
		const r = fuzzyRank('zzz', pool, (s) => s);
		expect(r).toHaveLength(0);
	});
});
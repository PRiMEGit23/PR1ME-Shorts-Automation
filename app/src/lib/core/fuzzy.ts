/**
 * Fuzzy subsequence matcher for the Command Palette (UX_ARCHITECTURE §8).
 * Subsequence scoring, 20 results max, ranking by score then position.
 */

export interface FuzzyMatch {
	score: number;
	indices: number[];
}

/** Score `query` against `candidate` as a subsequence; null if no match. */
export function fuzzyMatch(query: string, candidate: string): FuzzyMatch | null {
	const q = query.toLowerCase();
	const c = candidate.toLowerCase();
	if (q.length === 0) return { score: 0, indices: [] };
	if (q.length > c.length) return null;

	let score = 0;
	let qi = 0;
	let gap = 0;
	let first = -1;
	let last = -1;
	const indices: number[] = [];

	for (let ci = 0; ci < c.length && qi < q.length; ci++) {
		if (c[ci] === q[qi]) {
			if (first === -1) first = ci;
			indices.push(ci);
			if (last !== -1) gap += ci - last - 1;
			last = ci;
			score += 2;
			qi++;
		}
	}
	if (qi < q.length) return null;

	// bonus: contiguous runs, match at word starts, whole-word match
	let run = 0;
	for (let i = 1; i < indices.length; i++) {
		if (indices[i] === indices[i - 1]! + 1) run++;
	}
	score += run;
	const prev = first > 0 ? c[first - 1] : ' ';
	if (prev === ' ' || prev === '-' || prev === '/') score += 3;
	if (first === 0) score += 2;
	score -= gap;
	if (indices.length === c.length) score += 4;

	return { score, indices };
}

export interface Ranked<T> {
	item: T;
	match: FuzzyMatch;
}

/** Rank candidates by fuzzy score; max 20 results. */
export function fuzzyRank<T>(
	query: string,
	candidates: T[],
	titleOf: (item: T) => string
): Ranked<T>[] {
	if (query.length === 0) {
		return candidates.slice(0, 20).map((item) => ({
			item,
			match: { score: 0, indices: [] }
		}));
	}
	return candidates
		.map((item) => ({ item, match: fuzzyMatch(query, titleOf(item)) }))
		.filter((r): r is Ranked<T> => r.match !== null)
		.sort((a, b) => b.match.score - a.match.score || a.match.indices[0]! - b.match.indices[0]!)
		.slice(0, 20);
}
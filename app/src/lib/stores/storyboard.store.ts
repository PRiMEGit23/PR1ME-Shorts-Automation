/**
 * Storyboard store — Storyboard Workbench slice (IMPLEMENTATION_PLAN 2S4):
 * run bundle (manifest + report + scenes), KB scene-plan join, selection,
 * canvas viewport, and local (preview-only) approvals. Stores only apply
 * state; services call the bridge; the VM orchestrates (PRODUCT_LAYER §4/§5).
 */

import type { KnowledgeRow } from '$lib/models/knowledge';
import type { RenderAttempt } from '$lib/models/history';
import type {
	PromptShot,
	ScenePlan,
	StoryboardBundle,
	StoryboardScene
} from '$lib/models/storyboard';
import { PROMPT_SHOT_FIELDS, SCENE_PLAN_FIELDS } from '$lib/models/storyboard';

/** One scene card: backend scene + KB plan join + prompt pack shot. */
export interface SceneView {
	scene: StoryboardScene;
	/** Plan data from the KB row (null when no topic match — honest gaps). */
	plan: ScenePlan | null;
	shot: PromptShot | null;
	/** Plan duration in ms (null when the plan is unavailable). */
	durationMs: number | null;
	camera: string;
	lighting: string;
	composition: string;
	transition: string;
	motion: string;
	subject: string;
	material: string;
	objective: string;
	prompt: string;
	negativePrompt: string;
	rendering: string;
	candidates: CandidateView[];
}

/** One candidate thumbnail in a scene's strip (from render history). */
export interface CandidateView {
	attemptId: string;
	index: number;
	/** Absolute image path (attempt image_path resolved against run_dir). */
	imagePath: string | null;
	seed: number;
	status: string;
	qaScore: number | null;
	passed: boolean;
	hasOptimization: boolean;
}

export interface TimelineClip {
	sceneId: string;
	label: string;
	startMs: number;
	durationMs: number | null;
}

export const MIN_ZOOM = 0.5;
export const MAX_ZOOM = 2;
export const ZOOM_STEP = 0.25;

// ------------------------------------------------------- pure helpers

/** Parse the KB row's `scene_plan_json` / `image_prompt_pack_json`. */
export function parsePlanAndPack(row: KnowledgeRow | null | undefined): {
	plans: ScenePlan[];
	pack: PromptShot[];
} {
	const plans: ScenePlan[] = [];
	const pack: PromptShot[] = [];
	if (!row) return { plans, pack };
	const parseList = (cell: unknown): Record<string, unknown>[] => {
		if (typeof cell !== 'string' || !cell.trim()) return [];
		try {
			const v = JSON.parse(cell);
			return Array.isArray(v) ? v : [];
		} catch {
			return [];
		}
	};
	const str = (obj: Record<string, unknown>, key: string): string => {
		const v = obj[key];
		return typeof v === 'string' ? v : '';
	};
	for (const raw of parseList(row.scene_plan_json)) {
		const plan: Partial<ScenePlan> = { scene_id: str(raw, 'scene_id') };
		for (const field of SCENE_PLAN_FIELDS) {
			if (field !== 'scene_id') plan[field] = str(raw, field);
		}
		if (plan.scene_id) plans.push(plan as ScenePlan);
	}
	for (const raw of parseList(row.image_prompt_pack_json)) {
		const shot: Partial<PromptShot> = { shot_id: str(raw, 'shot_id') };
		for (const field of PROMPT_SHOT_FIELDS) {
			if (field !== 'shot_id') shot[field] = str(raw, field);
		}
		if (shot.shot_id) pack.push(shot as PromptShot);
	}
	return { plans, pack };
}

/** Parse `"6.2s"` / `"6.2"` / `"6.2 sec"` → seconds (null when unknown). */
export function parseDuration(value: string | undefined | null): number | null {
	if (!value) return null;
	const match = value.trim().match(/^(\d+(?:\.\d+)?)/);
	if (!match) return null;
	const seconds = Number(match[1]);
	return Number.isFinite(seconds) ? seconds : null;
}

/** Resolve an attempt image path against the run dir (relative → absolute). */
export function resolveImagePath(runDir: string, imagePath: string | null): string | null {
	if (!imagePath) return null;
	if (imagePath.startsWith('/') || /^[A-Za-z]:[\\/]/.test(imagePath)) return imagePath;
	return `${runDir.replace(/[\\/]$/, '')}/${imagePath}`;
}

/** Join bundle scenes with the KB row plan + prompt pack. */
export function buildSceneViews(
	bundle: StoryboardBundle,
	row: KnowledgeRow | null | undefined
): SceneView[] {
	const { plans, pack } = parsePlanAndPack(row);
	const planById = new Map(plans.map((p) => [p.scene_id, p]));
	const shotById = new Map(pack.map((s) => [s.shot_id, s]));
	return bundle.scenes.map((scene) => {
		const plan = planById.get(scene.scene_id) ?? null;
		const shot = shotById.get(scene.scene_id) ?? null;
		const candidates: CandidateView[] = (scene.history?.attempts ?? [])
			.map((attempt: RenderAttempt) => ({
				attemptId: attempt.attempt_id,
				index: attempt.index,
				imagePath: resolveImagePath(bundle.run_dir, attempt.image_path || null),
				seed: attempt.seed,
				status: attempt.status,
				qaScore: attempt.qa_report?.score ?? null,
				passed: attempt.status === 'passed',
				hasOptimization:
					!!attempt.optimization_report &&
					Object.keys(attempt.optimization_report).length > 0
			}))
			.sort((a, b) => a.index - b.index);
		return {
			scene,
			plan,
			shot,
			durationMs: plan ? secondsToMs(parseDuration(plan.duration)) : null,
			camera: plan?.camera ?? '—',
			lighting: plan?.lighting ?? '—',
			composition: plan?.composition ?? '—',
			transition: plan?.transition ?? '—',
			motion: plan?.motion ?? '—',
			subject: plan?.objects ?? '—',
			material: plan?.teaching_point ?? '—',
			objective: plan?.goal ?? '—',
			prompt:
				shot?.positive_prompt ??
				scene.history?.attempts[scene.history.attempts.length - 1]?.prompt ??
				'',
			negativePrompt:
				shot?.negative_prompt ??
				scene.history?.attempts[scene.history.attempts.length - 1]?.negative_prompt ??
				'',
			rendering: [shot?.render_notes, shot?.style].filter(Boolean).join(' · ') || '—',
			candidates
		};
	});
}

function secondsToMs(seconds: number | null): number | null {
	return seconds === null ? null : Math.round(seconds * 1000);
}

/** Scene clips in timeline order with running start offsets. */
export function timelineClips(views: SceneView[]): TimelineClip[] {
	const clips: TimelineClip[] = [];
	let cursor = 0;
	for (const view of views) {
		clips.push({
			sceneId: view.scene.scene_id,
			label: view.scene.scene_id,
			startMs: cursor,
			durationMs: view.durationMs
		});
		if (view.durationMs !== null) cursor += view.durationMs;
	}
	return clips;
}

/** Total runtime (null when no plan durations are known). */
export function totalRuntimeMs(clips: TimelineClip[]): number | null {
	const known = clips.filter((c) => c.durationMs !== null);
	if (known.length === 0) return null;
	return known.reduce((sum, c) => sum + (c.durationMs ?? 0), 0);
}

/** Wrap-around next/previous scene selection (N/P, ←/→). */
export function neighborSceneId(ids: string[], current: string | null, dir: 1 | -1): string | null {
	if (ids.length === 0) return null;
	if (current === null) return ids[dir === 1 ? 0 : ids.length - 1]!;
	const index = ids.indexOf(current);
	if (index === -1) return ids[0]!;
	return ids[(index + dir + ids.length) % ids.length]!;
}

// ------------------------------------------------------------- store

export class StoryboardStore {
	bundle: StoryboardBundle | null = $state(null);
	loading = $state(false);
	error: string | null = $state(null);

	/** KB row matched by manifest topic (scene plan + prompt pack source). */
	knowledgeRow: KnowledgeRow | null = $state(null);
	selectedSceneId: string | null = $state(null);
	/** Local, preview-only approvals: sceneId → candidate attempt id. */
	approvals: Map<string, string | null> = $state(new Map());

	zoom = $state(1);
	panX = $state(0);
	panY = $state(0);

	sceneViews = $derived(
		this.bundle ? buildSceneViews(this.bundle, this.knowledgeRow) : []
	);

	clips = $derived(timelineClips(this.sceneViews));
	totalRuntime = $derived(totalRuntimeMs(this.clips));
	/** Equal-width fallback when plan durations are unavailable. */
	hasDurations = $derived(this.clips.some((c) => c.durationMs !== null));

	selectedScene = $derived(
		this.sceneViews.find((v) => v.scene.scene_id === this.selectedSceneId) ?? null
	);

	/** The pipeline's winner is pre-approved by default (UX §5). */
	approvedCandidate = $derived.by(() => {
		if (!this.selectedScene) return null;
		const chosen = this.approvals.get(this.selectedScene.scene.scene_id);
		if (chosen !== undefined) return chosen;
		const winner = [...this.selectedScene.candidates]
			.reverse()
			.find((c) => c.passed);
		return winner?.attemptId ?? null;
	});

	/** Approved attempt for any scene (override or pre-approved winner). */
	approvedFor(sceneId: string): string | null {
		const chosen = this.approvals.get(sceneId);
		if (chosen !== undefined) return chosen;
		const view = this.sceneViews.find((v) => v.scene.scene_id === sceneId);
		const winner = [...(view?.candidates ?? [])].reverse().find((c) => c.passed);
		return winner?.attemptId ?? null;
	}

	/* ------------------------------------------------- mutators */

	applyBundle(bundle: StoryboardBundle, rows: KnowledgeRow[]): void {
		this.bundle = bundle;
		this.loading = false;
		this.error = null;
		const topic = bundle.topic.trim().toLowerCase();
		this.knowledgeRow =
			rows.find((r) => (r.topic ?? '').trim().toLowerCase() === topic) ?? null;
		const first = bundle.scenes[0]?.scene_id ?? null;
		this.selectedSceneId = this.sceneExists(first) ? first : null;
		this.approvals = new Map();
		this.zoom = 1;
		this.panX = 0;
		this.panY = 0;
	}

	selectScene(sceneId: string | null): void {
		if (sceneId === null || this.sceneExists(sceneId)) this.selectedSceneId = sceneId;
	}

	setLoading(loading: boolean): void {
		this.loading = loading;
	}

	setError(error: string | null): void {
		this.error = error;
		this.loading = false;
	}

	/** Preview-only approve override (never persisted — UX §11). */
	approveCandidate(sceneId: string, attemptId: string | null): void {
		this.approvals = new Map(this.approvals).set(sceneId, attemptId);
	}

	setZoom(zoom: number): void {
		this.zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
	}

	pan(dx: number, dy: number): void {
		this.panX += dx;
		this.panY += dy;
	}

	fitView(): void {
		this.zoom = 1;
		this.panX = 0;
		this.panY = 0;
	}

	private sceneExists(sceneId: string | null): boolean {
		return !!sceneId && !!this.bundle?.scenes.some((s) => s.scene_id === sceneId);
	}
}

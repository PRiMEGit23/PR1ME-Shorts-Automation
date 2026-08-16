/**
 * storyboard store — pure helpers + store lifecycle (IMPLEMENTATION_PLAN
 * 2S4 Storyboard): KB scene-plan/prompt-pack join, duration parsing, run-dir
 * image resolution, timeline clips/runtime, wrap-around selection, and the
 * preview-only approval override (winner pre-approved by default).
 */

import { describe, expect, it } from 'vitest';
import {
	buildSceneViews,
	neighborSceneId,
	parseDuration,
	resolveImagePath,
	timelineClips,
	totalRuntimeMs,
	StoryboardStore
} from '$lib/stores/storyboard.store';
import type { StoryboardBundle } from '$lib/models/storyboard';
import type { KnowledgeRow } from '$lib/models/knowledge';
import type { RenderHistory } from '$lib/models/history';

const ROW: KnowledgeRow = {
	topic: 'Bed Adhesion',
	difficulty: 'B',
	category: 'troubleshooting',
	subcategory: '',
	keywords: '[]',
	search_intent: '',
	viewer_level: 'B',
	script: 'Script.',
	scene_count: '2',
	scene_plan_json: JSON.stringify([
		{
			scene_id: 'S1',
			goal: 'Fix adhesion',
			teaching_point: 'Level the bed',
			camera: 'close-up',
			lens: 'macro',
			composition: 'rule of thirds',
			foreground: 'nozzle',
			background: 'bed',
			lighting: 'rim',
			motion: 'static',
			objects: 'spool',
			transition: 'cut',
			duration: '6.2s'
		},
		{
			scene_id: 'S2',
			goal: 'Show result',
			teaching_point: 'First layer',
			camera: 'tilt',
			lens: 'standard',
			composition: 'center',
			foreground: '',
			background: '',
			lighting: 'soft',
			motion: 'dolly-in',
			objects: 'part',
			transition: 'fade',
			duration: '4s'
		}
	]),
	image_prompt_pack_json: JSON.stringify([
		{
			shot_id: 'S1',
			positive_prompt: 'macro nozzle shot',
			negative_prompt: 'blurry',
			camera: 'close-up',
			lens: 'macro',
			lighting: 'rim',
			composition: 'rule of thirds',
			style: 'photoreal',
			render_notes: 'f/2.8'
		},
		{
			shot_id: 'S2',
			positive_prompt: 'first layer close view',
			negative_prompt: 'oversaturated',
			camera: 'tilt',
			lens: 'standard',
			lighting: 'soft',
			composition: 'center',
			style: 'photoreal',
			render_notes: ''
		}
	]),
	title: 'Bed Adhesion Fix'
};

const BUNDLE: StoryboardBundle = {
	run_id: '20260721_1200',
	topic: 'Bed Adhesion',
	run_dir: 'output/runs/20260721_1200/bed-adhesion',
	manifest: {
		version: '1',
		run_id: '20260721_1200',
		job_id: 'j1',
		topic: 'Bed Adhesion',
		status: 'completed',
		finished_at: null,
		run_dir: 'output/runs/20260721_1200/bed-adhesion',
		stages: [],
		final_artifacts: {}
	},
	report: null,
	scenes: [
		{
			scene_id: 'S1',
			image_path: 'images/S1.png',
			history: {
				topic: 'Bed Adhesion',
				scene_id: 'S1',
				seed: 42,
				max_attempts: 3,
				attempts: [
					{
						attempt_id: 'a1',
						index: 1,
						seed: 11,
						status: 'passed',
						image_path: 'attempts/S1/001.png',
						qa_report: { score: 88, passed: true, issues: [] },
						optimization_report: { note: 'n/a' },
						scene_id: 'S1',
						prompt: '',
						negative_prompt: '',
						workflow: {},
						workflow_profile: '',
						fingerprint: '',
						image_sha256: '',
						image_model: ''
					},
					{
						attempt_id: 'a2',
						index: 2,
						seed: 22,
						status: 'failed',
						image_path: '',
						qa_report: {},
						optimization_report: {},
						scene_id: 'S1',
						prompt: '',
						negative_prompt: '',
						workflow: {},
						workflow_profile: '',
						fingerprint: '',
						image_sha256: '',
						image_model: ''
					}
				]
			}
		},
		{ scene_id: 'S2', image_path: null, history: null }
	]
};

describe('pure helpers', () => {
	it('parseDuration extracts the leading number (s / s suffix)', () => {
		expect(parseDuration('6.2s')).toBe(6.2);
		expect(parseDuration('6.2')).toBe(6.2);
		expect(parseDuration('6.2 sec')).toBe(6.2);
		expect(parseDuration('')).toBeNull();
		expect(parseDuration('N/A')).toBeNull();
		expect(parseDuration(null)).toBeNull();
	});

	it('resolveImagePath keeps absolute paths, joins relative against run_dir', () => {
		expect(resolveImagePath('output/runs/r', 'attempts/S1/001.png')).toBe(
			'output/runs/r/attempts/S1/001.png'
		);
		expect(resolveImagePath('output/runs/r/', 'attempts/S1/001.png')).toBe(
			'output/runs/r/attempts/S1/001.png'
		);
		expect(resolveImagePath('output/runs/r', 'C:\\runs\\x.png')).toBe('C:\\runs\\x.png');
		expect(resolveImagePath('output/runs/r', null)).toBeNull();
	});

	it('neighborSceneId wraps around both directions', () => {
		expect(neighborSceneId(['S1', 'S2', 'S3'], 'S2', 1)).toBe('S3');
		expect(neighborSceneId(['S1', 'S2', 'S3'], 'S3', 1)).toBe('S1');
		expect(neighborSceneId(['S1', 'S2', 'S3'], 'S1', -1)).toBe('S3');
		expect(neighborSceneId(['S1', 'S2', 'S3'], null, 1)).toBe('S1');
		expect(neighborSceneId([], 'S1', 1)).toBeNull();
	});

	it('buildSceneViews joins plan + prompt pack and resolves images', () => {
		const views = buildSceneViews(BUNDLE, ROW);
		expect(views.map((v) => v.scene.scene_id)).toEqual(['S1', 'S2']);
		const s1 = views[0]!;
		expect(s1.camera).toBe('close-up');
		expect(s1.lighting).toBe('rim');
		expect(s1.composition).toBe('rule of thirds');
		expect(s1.motion).toBe('static');
		expect(s1.transition).toBe('cut');
		expect(s1.durationMs).toBe(6200);
		expect(s1.prompt).toBe('macro nozzle shot');
		expect(s1.negativePrompt).toBe('blurry');
		expect(s1.rendering).toBe('f/2.8 · photoreal');
		expect(s1.candidates.map((c) => c.attemptId)).toEqual(['a1', 'a2']);
		expect(s1.candidates[0]!.imagePath).toBe('output/runs/20260721_1200/bed-adhesion/attempts/S1/001.png');
		expect(s1.candidates[0]!.passed).toBe(true);
		expect(s1.candidates[0]!.hasOptimization).toBe(true);
		expect(s1.candidates[1]!.passed).toBe(false);
		expect(s1.candidates[1]!.imagePath).toBeNull();
	});

	it('buildSceneViews without a KB row shows honest gaps', () => {
		const views = buildSceneViews(BUNDLE, null);
		const s2 = views[1]!;
		expect(s2.plan).toBeNull();
		expect(s2.durationMs).toBeNull();
		expect(s2.camera).toBe('—');
		expect(s2.subject).toBe('—');
		expect(s2.prompt).toBe('');
		expect(s2.candidates).toEqual([]);
	});

	it('timelineClips + totalRuntimeMs accumulate only known durations', () => {
		const clips = timelineClips(buildSceneViews(BUNDLE, ROW));
		expect(clips).toEqual([
			{ sceneId: 'S1', label: 'S1', startMs: 0, durationMs: 6200 },
			{ sceneId: 'S2', label: 'S2', startMs: 6200, durationMs: 4000 }
		]);
		expect(totalRuntimeMs(clips)).toBe(10200);
		const unknown = timelineClips(buildSceneViews(BUNDLE, null));
		expect(totalRuntimeMs(unknown)).toBeNull();
	});
});

describe('StoryboardStore', () => {
	it('applyBundle selects the first scene and pre-approves the winner', () => {
		const store = new StoryboardStore();
		store.applyBundle(BUNDLE, [ROW]);
		expect(store.selectedSceneId).toBe('S1');
		expect(store.knowledgeRow?.topic).toBe('Bed Adhesion');
		expect(store.approvedFor('S1')).toBe('a1');
		expect(store.approvedCandidate).toBe('a1');
		expect(store.totalRuntime).toBe(10200);
		expect(store.hasDurations).toBe(true);
	});

	it('applyBundle with an unknown topic finds no KB row', () => {
		const store = new StoryboardStore();
		store.applyBundle({ ...BUNDLE, topic: 'Other Topic' }, [ROW]);
		expect(store.knowledgeRow).toBeNull();
	});

	it('approveCandidate overrides the winner locally (preview only)', () => {
		const store = new StoryboardStore();
		store.applyBundle(BUNDLE, [ROW]);
		store.approveCandidate('S1', 'a2');
		expect(store.approvedFor('S1')).toBe('a2');
		store.approveCandidate('S1', null);
		expect(store.approvedFor('S1')).toBeNull();
	});

	it('selectScene ignores unknown ids; zoom/pan clamp and reset', () => {
		const store = new StoryboardStore();
		store.applyBundle(BUNDLE, [ROW]);
		store.selectScene('S9');
		expect(store.selectedSceneId).toBe('S1');
		store.selectScene('S2');
		expect(store.selectedSceneId).toBe('S2');
		store.setZoom(9);
		expect(store.zoom).toBe(2);
		store.setZoom(0.1);
		expect(store.zoom).toBe(0.5);
		store.pan(10, -5);
		expect(store.panX).toBe(10);
		expect(store.panY).toBe(-5);
		store.fitView();
		expect(store.panX).toBe(0);
		expect(store.zoom).toBe(1);
	});

	it('hasDurations is false when no plan durations exist', () => {
		const store = new StoryboardStore();
		store.applyBundle(BUNDLE, []);
		expect(store.hasDurations).toBe(false);
		expect(store.totalRuntime).toBeNull();
		// the QA-passed candidate is still the pre-approved winner
		expect(store.approvedCandidate).toBe('a1');
	});
});
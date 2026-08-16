/**
 * 2S5 Render Queue store — reactive queue state.
 * Slice of AppStore (PRODUCT_LAYER §5).
 * Every value is plain JSON-serializable so devtools can snapshot/debug.
 * No duplicated state: derived values are computed from IPC passthrough.
 */

import { writable, get } from 'svelte/store';
import type { QueueItem, QueueStatus, HistoryRun, RenderProgress, RenderLogs, ProductionStats, ActiveRun, DashboardStats } from '$lib/models/render';

// ---------------------------------------------------------------------------
// Public store API
// ---------------------------------------------------------------------------

export interface QueueStoreI {
	// Reactive items (ordered by position)
	items: QueueItem[];

	// Reactive status snapshot from Rust `queue_status`
	status: QueueStatus;
}

// ---------------------------------------------------------------------------
// Internal store — Svelte $state pattern
// ---------------------------------------------------------------------------

function initialItems(): QueueItem[] {
	return [];
}

function initialStatus(): QueueStatus {
	return { active: [], tick: 0 };
}

function internalInitialState(): internal_QueueItem {
	return {
		id: '',
		topic: '',
		slug: '',
		seed: 42,
		maxAttempts: 3,
		publish: false,
		status: 'pending',
		runId: null,
		runDir: null,
		batchId: '',
		position: 0,
		stageStates: {},
		stageOrder: [],
		overallPct: 0,
		currentStage: null,
		stageProgress: null,
		etaMs: null,
		runtimeMs: 0,
		retries: 0,
		thumbnails: [],
		logLines: [],
		error: null,
		durationMs: null,
		finishedAt: null,
	};
}

interface internal_QueueItem {
	id: string;
	topic: string;
	slug: string;
	seed: number;
	maxAttempts: number;
	publish: boolean;
	status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'retrying';
	runId: string | null;
	runDir: string | null;
	batchId: string | null;
	position: number;
	stageStates: Record<string, string>; // stage_id → status
	stageOrder: string[]; // STAGE_ORDER from backend
	overallPct: number; // 0..100
	currentStage: string | null;
	stageProgress: string | null; // e.g. "4/15" or "30%"
	etaMs: number | null;
	runtimeMs: number;
	retries: number;
	thumbnails: string[];
	logLines: string[];
	error: string | null;
	durationMs: number | null;
	finishedAt: string | null;
}

// ---------------------------------------------------------------------------
// Public store API
// ---------------------------------------------------------------------------

export const queueStore = writable<QueueStoreI>({
	items: initialItems(),
	status: initialStatus(),
});

// ---------------------------------------------------------------------------
// Exported methods (outside $state so callers can `await store.method()`)
// ---------------------------------------------------------------------------

export function queueStore_addItem(store: typeof queueStore, item: Omit<QueueItem, 'id'>): string {
	const newId = `q-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
	const state = get(store);
	const newItem: QueueItem = {
		...item,
		id: newId,
		overallPct: 0,
		currentStage: null,
		stageProgress: null,
		etaMs: null,
		runtimeMs: 0,
		retries: 0,
		thumbnails: [],
		logLines: [],
		error: null,
		durationMs: null,
		finishedAt: null,
	};

	const updatedItems = [...state.items, newItem];
	store.set({
		...state,
		items: updatedItems,
		status: { ...state.status, active: [] },
	});

	return newId;
}

export function queueStore_removeItem(store: typeof queueStore, id: string): void {
	const state = get(store);
	const updatedItems = state.items.filter((i) => i.id !== id);
	store.set({
		...state,
		items: updatedItems,
		status: { ...state.status, active: [] },
	});
}

export function queueStore_setStatus(store: typeof queueStore, id: string, status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'retrying'): void {
	const state = get(store);
	const item = state.items.find((i) => i.id === id);
	if (!item) return;
	item.status = status;
	if (status === 'completed') {
		item.durationMs = new Date().getTime() - (item.runId ? 0 : 0);
		item.finishedAt = new Date().toISOString();
	} else if (status === 'cancelled') {
		item.error = 'job_aborted';
		item.finishedAt = new Date().toISOString();
	}
	store.set({
		...state,
		items: [...state.items],
		status: { ...state.status, active: [] },
	});
}

export function queueStore_reorder(store: typeof queueStore, oldPos: number, newPos: number): void {
	const state = get(store);
	const items = [...state.items];
	if (oldPos < 0 || oldPos >= items.length) {
		return;
	}
	const [moved] = items.splice(oldPos, 1);
	if (moved === undefined) {
		return;
	}
	items.splice(newPos, 0, moved);
	store.set({
		...state,
		items,
		status: { ...state.status, active: [] },
	});
}

export async function queueStore_startNext(store: typeof queueStore): Promise<void> {
	const state = get(store);
	const pending = state.items.find((i) => i.status === 'pending');
	if (!pending) return;

	state.items.forEach((i) => {
		i.status = i.id === pending.id ? 'running' : 'pending';
		i.currentStage = null;
		i.stageProgress = null;
		i.etaMs = null;
		i.runtimeMs = 0;
		i.retries = 0;
		i.thumbnails = [];
		i.logLines = [];
		i.error = null;
		i.durationMs = null;
		i.finishedAt = null;
	});

	store.set({
		...state,
		items: [...state.items],
		status: { ...state.status, active: [] },
	});
}

export function queueStore_pauseAll(store: typeof queueStore): void {
	const state = get(store);
	state.items.forEach((i) => (i.status = 'pending'));
	store.set({
		...state,
		items: [...state.items],
		status: { ...state.status, active: [] },
	});
}

export function queueStore_resumeAll(store: typeof queueStore): void {
	const state = get(store);
	state.items.forEach((i) => (i.status = i.status === 'pending' ? 'running' : i.status));
	store.set({
		...state,
		items: [...state.items],
		status: { ...state.status, active: [] },
	});
}

export function queueStore_clearCompleted(store: typeof queueStore): void {
	const state = get(store);
	const items = state.items.filter((i) => i.status !== 'completed');
	store.set({
		...state,
		items,
		status: { ...state.status, active: [] },
	});
}

// ---------------------------------------------------------------------------
// Derived selector helpers (convenient getters for components)
// ---------------------------------------------------------------------------

export const selectRunningItem = (store: typeof queueStore) =>
	get(store).items.find((i) => i.status === 'running');

export const selectCompletedItems = (store: typeof queueStore) =>
	get(store).items.filter((i) => i.status === 'completed');

export const selectFailedItems = (store: typeof queueStore) =>
	get(store).items.filter((i) => i.status === 'failed');

export const selectPendingItems = (store: typeof queueStore) =>
	get(store).items.filter((i) => i.status === 'pending');

// ---------------------------------------------------------------------------
// Bridge integration — keep status in sync with Rust queue_status
// ---------------------------------------------------------------------------

/** Call once at boot or workbench open to sync the Rust registry. */
export async function queueStore_syncStatus(store: typeof queueStore, bridge: import('$lib/core/bridge').Bridge): Promise<void> {
	const status = await bridge.queue_status();
	const state = get(store);
	store.set({
		...state,
		status,
	});
}
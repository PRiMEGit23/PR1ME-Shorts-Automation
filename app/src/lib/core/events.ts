/**
 * Typed Tauri event subscriptions (PRODUCT_LAYER_ARCHITECTURE §6 — event payloads).
 * Rust → UI streaming: runs, fs changes, generation queue, updater.
 */

import { listen } from '@tauri-apps/api/event';

export type BridgeEventName =
	| 'run:started'
	| 'run:stage'
	| 'run:progress'
	| 'run:candidate'
	| 'run:completed'
	| 'run:failed'
	| 'run:logline'
	| 'fs:change'
	| 'generate:queued'
	| 'updater:status';

export interface EventMap {
	'run:started': { runId: string; processId: number; topic: string; episodeSlug: string };
	'run:stage': { runId: string; stageId: string; status: string; offsetMs: number };
	'run:progress': { runId: string; stageId: string; attempt?: number | null; detail?: string | null };
	'run:candidate': { runId: string; sceneId: string; attemptId: string; imagePath: string };
	'run:completed': {
		runId: string;
		status: string;
		runDir: string;
		report: Record<string, unknown>;
	};
	'run:failed': { runId: string; error: string };
	'run:logline': { runId: string; line: string };
	'fs:change': { path: string; kind: 'create' | 'modify' | 'remove' };
	'generate:queued': { runId: string; position: number };
	'updater:status': { state: string; version?: string | null; progress?: number | null };
}

export type EventTransport = (
	event: BridgeEventName,
	handler: (payload: unknown) => void
) => () => void;

const tauriEventTransport: EventTransport = (event, handler) => {
	const unlisten = listen<unknown>(event, (e) => handler(e.payload));
	return () => {
		void unlisten.then((fn) => fn());
	};
};

export class EventBus {
	constructor(private readonly transport: EventTransport = tauriEventTransport) {}

	/** Subscribe; returns an unsubscribe function. */
	on<K extends keyof EventMap>(event: K, handler: (payload: EventMap[K]) => void): () => void {
		return this.transport(event, (payload) => handler(payload as EventMap[K]));
	}
}
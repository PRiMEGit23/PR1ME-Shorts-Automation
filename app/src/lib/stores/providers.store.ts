/**
 * Providers store — `providers` slice (PRODUCT_LAYER §5): per-provider
 * health state (status/message/latency/lastChecked) + busy flags for the
 * Connection Center. Every value is plain JSON-serializable.
 */

import type { HealthState, HealthStatus, ProviderId } from '$lib/models/providers';

export interface HealthEntry {
	status: HealthStatus;
	message: string | null;
	latencyMs: number | null;
	lastChecked: string | null;
}

const INITIAL: HealthEntry = { status: 'unknown', message: null, latencyMs: null, lastChecked: null };

function initialMap(): Record<ProviderId, HealthEntry> {
	return {
		ollama: { ...INITIAL },
		deepseek: { ...INITIAL },
		comfyui: { ...INITIAL },
		kokoro: { ...INITIAL },
		ffmpeg: { ...INITIAL },
		youtube: { ...INITIAL },
		instagram: { ...INITIAL }
	};
}

export class ProvidersStore {
	health: Record<ProviderId, HealthEntry> = $state(initialMap());
	busy: Record<ProviderId, boolean> = $state({
		ollama: false,
		deepseek: false,
		comfyui: false,
		kokoro: false,
		ffmpeg: false,
		youtube: false,
		instagram: false
	});

	/** Store mutators — services/VM return results, the store applies them. */

	beginCheck(id: ProviderId): void {
		this.busy[id] = true;
		this.health[id] = { ...this.health[id], status: 'checking' };
	}

	endCheck(id: ProviderId, state: HealthState): void {
		this.busy[id] = false;
		this.health[id] = {
			status: state.status,
			message: state.message ?? null,
			latencyMs: state.latency_ms ?? null,
			lastChecked: new Date().toISOString()
		};
	}

	failCheck(id: ProviderId, message: string): void {
		this.busy[id] = false;
		this.health[id] = {
			status: 'error',
			message,
			latencyMs: null,
			lastChecked: new Date().toISOString()
		};
	}

	applyAll(states: HealthState[]): void {
		for (const s of states) {
			this.endCheck(s.provider as ProviderId, s);
		}
	}
}
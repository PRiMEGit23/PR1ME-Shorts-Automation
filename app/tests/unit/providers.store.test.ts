/**
 * providers store — health entries + busy flags (PRODUCT_LAYER §5).
 */

import { describe, expect, it } from 'vitest';
import { ProvidersStore } from '$lib/stores/providers.store';
import type { HealthState } from '$lib/models/providers';

function make() {
	return new ProvidersStore();
}

describe('ProvidersStore', () => {
	it('starts every provider unknown and idle', () => {
		const s = make();
		expect(Object.keys(s.health).sort()).toEqual(
			['ollama', 'deepseek', 'comfyui', 'kokoro', 'ffmpeg', 'youtube', 'instagram'].sort()
		);
		for (const entry of Object.values(s.health)) {
			expect(entry.status).toBe('unknown');
			expect(entry.latencyMs).toBeNull();
			expect(entry.lastChecked).toBeNull();
		}
		expect(Object.values(s.busy).every((b) => b === false)).toBe(true);
	});

	it('beginCheck marks busy + checking', () => {
		const s = make();
		s.beginCheck('ollama');
		expect(s.busy['ollama']).toBe(true);
		expect(s.health['ollama'].status).toBe('checking');
	});

	it('endCheck applies the state with an ISO lastChecked', () => {
		const s = make();
		s.endCheck('comfyui', { provider: 'comfyui', status: 'ok', message: 'HTTP 200', latency_ms: 12 });
		expect(s.health['comfyui']).toMatchObject({ status: 'ok', message: 'HTTP 200', latencyMs: 12 });
		expect(new Date(s.health['comfyui'].lastChecked!).toISOString()).toBe(s.health['comfyui'].lastChecked);
		expect(s.busy['comfyui']).toBe(false);
	});

	it('failCheck records an error without latency', () => {
		const s = make();
		s.failCheck('ffmpeg', 'binary not found');
		expect(s.health['ffmpeg']).toMatchObject({ status: 'error', message: 'binary not found', latencyMs: null });
		expect(s.health['ffmpeg'].lastChecked).not.toBeNull();
	});

	it('applyAll applies a batch of states', () => {
		const s = make();
		const states: HealthState[] = [
			{ provider: 'ollama', status: 'ok', latency_ms: 5 },
			{ provider: 'youtube', status: 'error', message: 'no token' }
		];
		s.applyAll(states);
		expect(s.health['ollama'].status).toBe('ok');
		expect(s.health['ollama'].latencyMs).toBe(5);
		expect(s.health['youtube'].status).toBe('error');
		expect(s.health['youtube'].message).toBe('no token');
	});
});
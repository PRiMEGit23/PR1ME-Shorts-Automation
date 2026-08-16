/**
 * Providers service — health probes + `.env` reveal. The ONLY layer that
 * touches the bridge for providers (PRODUCT_LAYER §4). Reveal uses the
 * shell plugin (Tauri only; browser dev is a no-op).
 */

import { open } from '@tauri-apps/plugin-shell';

import type { Bridge } from '$lib/core/bridge';
import type { HealthState, ProviderId } from '$lib/models/providers';

export class ProvidersService {
	constructor(private readonly bridge: Bridge) {}

	health(provider: ProviderId): Promise<HealthState> {
		return this.bridge.providers_health(provider);
	}

	healthAll(): Promise<HealthState[]> {
		return this.bridge.providers_health_all();
	}

	/** Reveal `.env` — opens the file with the OS default app (UX §15). */
	async revealEnv(repoRoot: string): Promise<void> {
		if (!('__TAURI_INTERNALS__' in window)) return;
		await open(`${repoRoot}/.env`);
	}
}
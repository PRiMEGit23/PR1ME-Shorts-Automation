/**
 * Settings store — holds the loaded SettingsModel; applies results from the
 * settings service (PRODUCT_LAYER §4: services return, stores apply).
 */

import type { SettingsService } from '$lib/services/settings.service';
import type { SettingsModel } from '$lib/models/settings';

export class SettingsStore {
	model: SettingsModel | null = $state(null);
	loading: boolean = $state(false);
	error: string | null = $state(null);

	async load(service: SettingsService): Promise<void> {
		this.loading = true;
		this.error = null;
		try {
			this.model = await service.load();
		} catch (err) {
			this.error = err instanceof Error ? err.message : String(err);
		} finally {
			this.loading = false;
		}
	}

	async save(service: SettingsService): Promise<void> {
		if (!this.model) return;
		this.error = null;
		try {
			await service.save(this.model);
		} catch (err) {
			this.error = err instanceof Error ? err.message : String(err);
		}
	}
}
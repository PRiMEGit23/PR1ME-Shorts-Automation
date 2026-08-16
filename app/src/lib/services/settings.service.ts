/**
 * Settings service — load/save `.env` via the bridge. The ONLY layer that
 * touches the bridge for settings (PRODUCT_LAYER §4).
 */

import type { Bridge } from '$lib/core/bridge';
import type { SettingsModel } from '$lib/models/settings';

export class SettingsService {
	constructor(private readonly bridge: Bridge) {}

	async load(): Promise<SettingsModel> {
		return this.bridge.settings_load();
	}

	async save(model: SettingsModel): Promise<void> {
		await this.bridge.settings_save(model);
	}
}
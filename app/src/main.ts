/**
 * Bootstrap — stores → bridge → shell (PRODUCT_LAYER §3: src/main.ts).
 */

import { AppStore } from '$lib/stores/app.store';
import type { AppServices } from '$lib/core/di';

export const store = new AppStore();

export async function bootstrap(services: AppServices): Promise<AppStore> {
	await store.boot(services);
	return store;
}
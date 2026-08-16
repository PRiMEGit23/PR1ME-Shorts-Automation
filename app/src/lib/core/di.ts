/**
 * DI container — AppServices. The ONLY place wiring happens.
 * Views → ViewModels → Services → Bridge (PRODUCT_LAYER §4).
 */

import { Bridge, type IpcTransport } from '$lib/core/bridge';
import { EventBus, type EventTransport } from '$lib/core/events';
import { SettingsService } from '$lib/services/settings.service';
import { LayoutService } from '$lib/services/layout.service';
import { ProvidersService } from '$lib/services/providers.service';

export interface AppServices {
	bridge: Bridge;
	events: EventBus;
	settings: SettingsService;
	layout: LayoutService;
	providers: ProvidersService;
}

export function createServices(
	transport?: IpcTransport,
	eventTransport?: EventTransport
): AppServices {
	const bridge = new Bridge(transport);
	const events = new EventBus(eventTransport);
	return {
		bridge,
		events,
		settings: new SettingsService(bridge),
		layout: new LayoutService(bridge),
		providers: new ProvidersService(bridge)
	};
}

/** Global singleton — created by main.ts bootstrap, used by components/stores. */
export const di: AppServices = createServices();
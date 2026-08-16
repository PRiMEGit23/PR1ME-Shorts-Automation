/**
 * AppStore — root store, slice wiring (PRODUCT_LAYER §5).
 * Boot sequence (main.ts): stores → bridge → shell.
 */

import type { AppServices } from '$lib/core/di';
import { UiStore } from '$lib/stores/ui.store';
import { SettingsStore } from '$lib/stores/settings.store';
import { LayoutStore } from '$lib/stores/layout.store';
import { EditorStore } from '$lib/stores/editor.store';
import { ProvidersStore } from '$lib/stores/providers.store';
import { ConnectionsVm } from '$lib/viewmodels/connections.vm';
import type { AppVersion } from '$lib/core/bridge';

export interface BootPhase {
	label: string;
	done: boolean;
}

const BOOT_PHASES: { id: string; label: string }[] = [
	{ id: 'settings', label: 'loading settings' },
	{ id: 'version', label: 'probing pr1me' },
	{ id: 'providers', label: 'probing providers' }
];

export class AppStore {
	ui: UiStore = $state(new UiStore());
	settings: SettingsStore = $state(new SettingsStore());
	layout: LayoutStore = $state(new LayoutStore());
	editor: EditorStore = $state(new EditorStore());
	providers: ProvidersStore = $state(new ProvidersStore());
	connections: ConnectionsVm | null = $state(null);

	version: AppVersion | null = $state(null);
	bootPhase: string = $state('');
	bootError: string | null = $state(null);

	/** Boot: settings → version probe → provider probes → shell. */
	async boot(services: AppServices): Promise<void> {
		for (const phase of BOOT_PHASES) {
			this.bootPhase = phase.label;
			try {
				if (phase.id === 'settings') {
					await this.settings.load(services.settings);
				} else if (phase.id === 'version') {
					this.version = await services.bridge.app_version();
				} else if (phase.id === 'providers') {
					this.connections = new ConnectionsVm(this.ui, this.settings, this.providers, services);
					await this.connections.testAll();
				}
			} catch (err) {
				this.bootError = err instanceof Error ? err.message : String(err);
			}
		}
		this.bootPhase = '';
		this.ui.setBooted();
	}

	/** Save the current workbench layout (Cmd+S). */
	async saveLayout(services: AppServices): Promise<void> {
		try {
			await this.layout.persist(services.layout);
		} catch (err) {
			this.ui.pushToast('error', 'Layout not saved', {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}
}
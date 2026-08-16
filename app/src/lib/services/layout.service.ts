/**
 * Layout service — workbench presets (UX_ARCHITECTURE §18) + persistence
 * via `layout_save` → `config/ui-layout.json` (PRODUCT_LAYER §7).
 */

import type { Bridge } from '$lib/core/bridge';
import type { WorkbenchId } from '$lib/stores/ui.store';

export type PanelId = 'explorer' | 'assets' | 'inspector' | 'timeline' | 'terminal';

export interface ZoneState {
	left: PanelId[];
	right: PanelId[];
	bottom: PanelId[];
}

export interface SplitState {
	id: string;
	direction: 'horizontal' | 'vertical';
	sizes: number[];
}

export interface LayoutState {
	zones: ZoneState;
	sizes: { left: number; right: number; bottom: number };
	splits: SplitState[];
	pinned: Record<PanelId, boolean>;
	collapsed: { left: boolean; right: boolean; bottom: boolean };
}

/** Default panel placement (UX §2.2 / §13). */
export const PANEL_DEFAULT_ZONE: Record<PanelId, keyof ZoneState> = {
	explorer: 'left',
	assets: 'left',
	inspector: 'right',
	timeline: 'bottom',
	terminal: 'bottom'
};

/** Per-workbench default layouts (UX_ARCHITECTURE §18 — locked). */
export const DEFAULT_LAYOUTS: Record<WorkbenchId, LayoutState> = {
	library: {
		zones: { left: ['explorer'], right: [], bottom: [] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: true, bottom: true }
	},
	script: {
		zones: { left: ['explorer'], right: ['inspector'], bottom: ['timeline'] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: false, bottom: false }
	},
	storyboard: {
		zones: { left: ['explorer'], right: ['inspector'], bottom: ['terminal'] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: false, bottom: false }
	},
	workflow: {
		zones: { left: ['explorer'], right: ['inspector'], bottom: ['terminal'] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: false, bottom: false }
	},
	render: {
		zones: { left: ['explorer'], right: ['inspector'], bottom: ['terminal'] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: false, bottom: false }
	},
	edit: {
		zones: { left: ['explorer'], right: ['inspector'], bottom: [] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: false, bottom: true }
	},
	deliver: {
		zones: { left: ['explorer'], right: ['inspector'], bottom: ['terminal'] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: false, bottom: false }
	},
	insights: {
		zones: { left: ['explorer'], right: [], bottom: ['terminal'] },
		sizes: { left: 280, right: 320, bottom: 200 },
		splits: [],
		pinned: { explorer: true, assets: true, inspector: true, timeline: true, terminal: true },
		collapsed: { left: false, right: true, bottom: false }
	}
};

export class LayoutService {
	constructor(private readonly bridge: Bridge) {}

	preset(workbench: WorkbenchId): LayoutState {
		return structuredClone(DEFAULT_LAYOUTS[workbench]);
	}

	async persist(workbench: WorkbenchId, layout: LayoutState): Promise<void> {
		await this.bridge.layout_save(workbench, layout);
	}
}
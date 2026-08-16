/**
 * Layout store — per-workbench layout state; workbench switching applies the
 * documented presets (UX_ARCHITECTURE §18). Persisted via layout.service.
 */

import {
	DEFAULT_LAYOUTS,
	PANEL_DEFAULT_ZONE,
	type LayoutService,
	type LayoutState,
	type PanelId
} from '$lib/services/layout.service';
import type { WorkbenchId } from '$lib/stores/ui.store';

export { type LayoutState, type PanelId, type SplitState } from '$lib/services/layout.service';

export const PANEL_IDS: PanelId[] = ['explorer', 'assets', 'inspector', 'timeline', 'terminal'];

const CLAMP: Record<'left' | 'right' | 'bottom', { min: number; max: number }> = {
	left: { min: 200, max: 480 },
	right: { min: 200, max: 480 },
	bottom: { min: 120, max: 480 }
};

export class LayoutStore {
	states: Record<WorkbenchId, LayoutState> = $state(structuredClone(DEFAULT_LAYOUTS));
	active: WorkbenchId = $state('library');

	current(): LayoutState {
		return this.states[this.active];
	}

	setWorkbench(id: WorkbenchId): void {
		this.active = id;
	}

	resetWorkbench(id: WorkbenchId): void {
		this.states[id] = structuredClone(DEFAULT_LAYOUTS[id]);
	}

	/** Activity bar toggle: show panel in its default zone / hide it. */
	togglePanel(panel: PanelId): void {
		const layout = this.states[this.active];
		const zone = PANEL_DEFAULT_ZONE[panel];
		const zones = layout.zones[zone];
		if (zones.includes(panel)) {
			layout.zones[zone] = zones.filter((p) => p !== panel);
		} else {
			layout.zones[zone] = [...zones, panel];
		}
	}

	/**
	 * Pin/unpin (VDS §39): pinned = always visible; unpinned = auto-hide to
	 * the zone edge strip (28px icon rail).
	 */
	pin(panel: PanelId, pinned: boolean): void {
		const s = this.states[this.active];
		s.pinned = { ...s.pinned, [panel]: pinned };
		const def = PANEL_DEFAULT_ZONE[panel];
		const zones = s.zones;
		if (pinned && !zones[def].includes(panel)) {
			s.zones = { ...zones, [def]: [...zones[def], panel] };
		} else if (!pinned && zones[def].includes(panel)) {
			s.zones = { ...zones, [def]: zones[def].filter((p) => p !== panel) };
		}
	}

	isPanelPinned(panel: PanelId): boolean {
		return this.states[this.active].pinned[panel];
	}

	isPanelVisible(panel: PanelId): boolean {
		const layout = this.states[this.active];
		return (
			layout.zones.left.includes(panel) ||
			layout.zones.right.includes(panel) ||
			layout.zones.bottom.includes(panel)
		);
	}

	setZoneSize(side: keyof LayoutState['sizes'], px: number): void {
		const clamp = CLAMP[side];
		this.states[this.active].sizes[side] = Math.min(clamp.max, Math.max(clamp.min, px));
	}

	toggleCollapse(side: keyof LayoutState['collapsed']): void {
		const c = this.states[this.active].collapsed;
		this.states[this.active].collapsed = { ...c, [side]: !c[side] };
	}

	/** Cmd+S — persist current workbench layout. */
	async persist(service: LayoutService): Promise<void> {
		await service.persist(this.active, this.current());
	}
}
/**
 * Production models — mirror of `config/productions/<slug>/production.json`
 * (product-owned, backend-untouched). Contract: UX_ARCHITECTURE §9.1,
 * PRODUCT_LAYER_ARCHITECTURE §6 command table.
 */

export type PublishDefault = 'dryRun' | 'real';

export type EpisodeStatus =
	| 'drafted'
	| 'queued'
	| 'rendering'
	| 'review'
	| 'approved'
	| 'rendered'
	| 'delivered';

export interface PipelinePolicy {
	defaultSeed: number;
	maxAttempts: number;
	publishDefault: PublishDefault;
}

export interface ProductionScope {
	category: string | null;
	difficulty: string | null;
}

export interface RunRefs {
	runId: string | null;
	runDir: string | null;
}

export interface DeliverInfo {
	titleOverride: string | null;
	descriptionOverride: string | null;
	published: boolean;
}

export interface EpisodeRecord {
	topic: string;
	rowIndex: number;
	status: EpisodeStatus;
	seed: number | null;
	approvals: Record<string, string | null>;
	run: RunRefs;
	deliver: DeliverInfo;
}

export interface ProductionIdentity {
	id: string;
	name: string;
	slug: string;
	created: string;
	updated: string;
}

export interface ProductionUi {
	layouts: Record<string, unknown>;
	paletteRecents: string[];
}

export interface ProductionModel {
	identity: ProductionIdentity;
	policy: PipelinePolicy;
	scope: ProductionScope;
	episodes: EpisodeRecord[];
	ui: ProductionUi;
}

export interface ProductionSummary {
	id: string;
	name: string;
	slug: string;
	created: string;
	updated: string;
	episodeCount: number;
}

export interface ProductionCreateArgs {
	name: string;
	template?: string | null;
	policy: PipelinePolicy;
}
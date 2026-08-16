/**
 * Settings model — the `.env` surface + repo directories.
 * Contract: Rust `settings_load` / `settings_save` (BACKEND_ARCHITECTURE §5).
 */

import type { EnvMap } from '$lib/core/config';

export interface SettingsModel {
	repo_root: string;
	prompts_dir: string;
	work_dir: string;
	temp_dir: string;
	assets_dir: string;
	/** Full `.env` map (all keys, including legacy non-PR1ME_* keys). */
	env: EnvMap;
}

export interface SettingsModelView {
	model: SettingsModel;
	/** Masked display of a secret value (never the raw value). */
	maskSecret(value: string | undefined): string;
}

export function maskSecret(value: string | undefined): string {
	if (!value) return '';
	if (value.length <= 8) return '••••••••';
	return `${value.slice(0, 4)}••••${value.slice(-4)}`;
}
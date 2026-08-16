/**
 * Connections VM — Connection Center orchestration (UX_ARCHITECTURE §15,
 * PRODUCT_LAYER §4): inline config draft per provider, validation,
 * `.env` commit (provider keys only — never unrelated keys), Test
 * (live health), Reveal `.env`. Plain class; testable without Tauri.
 */

import { maskSecret } from '$lib/models/settings';
import { PROVIDERS, type ProviderId } from '$lib/models/providers';
import type { AppServices } from '$lib/core/di';
import type { UiStore } from '$lib/stores/ui.store';
import type { SettingsStore } from '$lib/stores/settings.store';
import type { ProvidersStore } from '$lib/stores/providers.store';

export type FieldKind = 'url' | 'text' | 'secret' | 'path';

export interface ProviderField {
	envKey: string;
	label: string;
	kind: FieldKind;
	required?: boolean;
	default: string;
}

/** Key config fields per provider (BACKEND_ARCHITECTURE §5). */
export const PROVIDER_FIELDS: Record<ProviderId, ProviderField[]> = {
	ollama: [
		{ envKey: 'PR1ME_OLLAMA_BASE_URL', label: 'Base URL', kind: 'url', required: true, default: 'http://127.0.0.1:11434/v1' },
		{ envKey: 'PR1ME_OLLAMA_MODEL', label: 'Model', kind: 'text', required: true, default: 'qwen2.5:7b' },
		{ envKey: 'PR1ME_OLLAMA_API_KEY', label: 'API key', kind: 'secret', default: '' }
	],
	deepseek: [
		{ envKey: 'PR1ME_DEEPSEEK_API_KEY', label: 'API key', kind: 'secret', required: true, default: '' },
		{ envKey: 'PR1ME_DEEPSEEK_BASE_URL', label: 'Base URL', kind: 'url', default: 'https://api.deepseek.com' },
		{ envKey: 'PR1ME_DEEPSEEK_MODEL', label: 'Model', kind: 'text', default: 'deepseek-chat' }
	],
	comfyui: [{ envKey: 'PR1ME_COMFYUI_BASE_URL', label: 'Base URL', kind: 'url', required: true, default: 'http://127.0.0.1:8188' }],
	kokoro: [
		{ envKey: 'PR1ME_VOICE_BASE_URL', label: 'Base URL', kind: 'url', default: 'http://127.0.0.1:8890' },
		{ envKey: 'PR1ME_VOICE_VOICE', label: 'Voice', kind: 'text', default: 'af_heart' }
	],
	ffmpeg: [
		{ envKey: 'PR1ME_AUDIO_FFMPEG_BIN', label: 'Audio binary', kind: 'path', required: true, default: 'ffmpeg' },
		{ envKey: 'PR1ME_RENDER_FFMPEG_BIN', label: 'Render binary', kind: 'path', required: true, default: 'ffmpeg' }
	],
	youtube: [
		{ envKey: 'PR1ME_YOUTUBE_REFRESH_TOKEN', label: 'Refresh token', kind: 'secret', default: '' },
		{ envKey: 'PR1ME_YOUTUBE_CLIENT_ID', label: 'Client ID', kind: 'text', default: '' },
		{ envKey: 'PR1ME_YOUTUBE_CLIENT_SECRET', label: 'Client secret', kind: 'secret', default: '' }
	],
	instagram: []
};

/** Start hints for local providers that are not detected (UX §15). */
const START_HINTS: Partial<Record<ProviderId, string>> = {
	ollama: 'Start: ollama serve — http://127.0.0.1:11434',
	comfyui: 'Start: run ComfyUI — http://127.0.0.1:8188',
	kokoro: 'Start: kokoro server — http://127.0.0.1:8890',
	ffmpeg: 'Install ffmpeg and add it to PATH'
};

const LOCAL: ProviderId[] = ['ollama', 'comfyui', 'kokoro', 'ffmpeg'];

/* ---------------------------------------------------------- validation */

export function validateUrl(value: string): boolean {
	try {
		const url = new URL(value);
		return url.protocol === 'http:' || url.protocol === 'https:';
	} catch {
		return false;
	}
}

export function validatePath(value: string): boolean {
	const v = value.trim();
	if (!v) return false;
	if (/\s/.test(v)) return false;
	// absolute (Windows drive or UNC) — relative/bare names are allowed too
	if (v.includes('\\') || v.includes('/')) {
		return /^[A-Za-z]:[\\/]/.test(v) || v.startsWith('\\\\') || v.startsWith('/');
	}
	return true;
}

export function validateFields(
	fields: ProviderField[],
	values: Record<string, string>
): string[] {
	const errors: string[] = [];
	for (const f of fields) {
		const v = (values[f.envKey] ?? '').trim();
		if (f.required && !v) {
			errors.push(`${f.label} is required`);
			continue;
		}
		if (!v) continue;
		if (f.kind === 'url' && !validateUrl(v)) errors.push(`${f.label} must be a valid http(s) URL`);
		if (f.kind === 'path' && !validatePath(v)) errors.push(`${f.label} must be a command or absolute path`);
	}
	return errors;
}

/* --------------------------------------------------------------- VM */

export class ConnectionsVm {
	draft: Record<ProviderId, Record<string, string>> = $state({
		ollama: {},
		deepseek: {},
		comfyui: {},
		kokoro: {},
		ffmpeg: {},
		youtube: {},
		instagram: {}
	});
	editing: Record<ProviderId, boolean> = $state({
		ollama: false,
		deepseek: false,
		comfyui: false,
		kokoro: false,
		ffmpeg: false,
		youtube: false,
		instagram: false
	});
	errors: Record<ProviderId, string[]> = $state({
		ollama: [],
		deepseek: [],
		comfyui: [],
		kokoro: [],
		ffmpeg: [],
		youtube: [],
		instagram: []
	});
	saving: Record<ProviderId, boolean> = $state({
		ollama: false,
		deepseek: false,
		comfyui: false,
		kokoro: false,
		ffmpeg: false,
		youtube: false,
		instagram: false
	});

	constructor(
		private readonly ui: UiStore,
		private readonly settings: SettingsStore,
		private readonly providers: ProvidersStore,
		private readonly services: AppServices
	) {}

	labelFor(id: ProviderId): string {
		return PROVIDERS.find((p) => p.id === id)?.label ?? id;
	}

	/** Open: ensure settings are loaded, then refresh all health quietly. */
	async open(): Promise<void> {
		if (!this.settings.model) await this.settings.load(this.services.settings);
		await this.testAll();
	}

	startEdit(id: ProviderId): void {
		const env = this.settings.model?.env ?? {};
		const draft: Record<string, string> = {};
		for (const f of PROVIDER_FIELDS[id]) {
			// secrets start empty so an untouched draft never holds raw values
			draft[f.envKey] = f.kind === 'secret' ? '' : (env[f.envKey] ?? '');
		}
		this.draft[id] = draft;
		this.errors[id] = [];
		this.editing[id] = true;
	}

	cancelEdit(id: ProviderId): void {
		this.editing[id] = false;
		this.draft[id] = {};
		this.errors[id] = [];
	}

	setField(id: ProviderId, envKey: string, value: string): void {
		this.draft[id] = { ...this.draft[id], [envKey]: value };
	}

	/** Display value: raw for editable text, masked for secrets (editing
	 *  secrets show the draft; untouched = '' so the placeholder shows the
	 *  mask and no raw secret ever sits in the input). */
	displayValue(id: ProviderId, field: ProviderField): string {
		const env = this.settings.model?.env ?? {};
		const draft = this.draft[id]?.[field.envKey] ?? '';
		if (field.kind === 'secret') {
			if (this.editing[id]) return draft;
			return env[field.envKey] ? maskSecret(env[field.envKey]) : '';
		}
		return this.editing[id] ? draft : (env[field.envKey] ?? '');
	}

	/** Empty secret drafts mean "keep existing" — the placeholder shows the mask. */
	secretPlaceholder(id: ProviderId, field: ProviderField): string {
		const raw = this.settings.model?.env?.[field.envKey] ?? '';
		return raw ? maskSecret(raw) : 'not set';
	}

	validate(id: ProviderId): string[] {
		return validateFields(PROVIDER_FIELDS[id], this.draft[id] ?? {});
	}

	/**
	 * Commit the draft to `.env` — touches ONLY this provider's keys
	 * (settings_save preserves every other key; no duplicates possible).
	 * Returns false when validation fails.
	 */
	async commit(id: ProviderId): Promise<boolean> {
		const errs = this.validate(id);
		this.errors[id] = errs;
		if (errs.length > 0) return false;

		const model = this.settings.model;
		if (!model) return false;

		const env = { ...model.env };
		for (const f of PROVIDER_FIELDS[id]) {
			const v = (this.draft[id]?.[f.envKey] ?? '').trim();
			if (f.kind === 'secret') {
				if (v) env[f.envKey] = v; // untouched secret → keep existing
				continue;
			}
			// empty → default when one exists, otherwise unset
			if (v) env[f.envKey] = v;
			else if (f.default) env[f.envKey] = f.default;
			else delete env[f.envKey];
		}
		model.env = env;

		this.saving[id] = true;
		try {
			await this.settings.save(this.services.settings);
			this.ui.pushToast('success', `${this.labelFor(id)} saved`, {
				message: 'Written to .env'
			});
			this.cancelEdit(id);
			await this.test(id);
			return true;
		} catch (err) {
			this.ui.pushToast('error', `${this.labelFor(id)} not saved`, {
				message: err instanceof Error ? err.message : String(err)
			});
			return false;
		} finally {
			this.saving[id] = false;
		}
	}

	/** Live connection test (UX §15). `notify` toasts on error state. */
	async test(id: ProviderId, notify = true): Promise<void> {
		if (this.providers.busy[id]) return;
		this.providers.beginCheck(id);
		try {
			const state = await this.services.providers.health(id);
			this.providers.endCheck(id, state);
			if (notify && state.status === 'error') {
				this.ui.pushToast('error', `${this.labelFor(id)} unreachable`, {
					message: state.message ?? 'health check failed'
				});
			}
		} catch (err) {
			this.providers.failCheck(id, err instanceof Error ? err.message : String(err));
			if (notify) {
				this.ui.pushToast('error', `${this.labelFor(id)} check failed`, {
					message: err instanceof Error ? err.message : String(err)
				});
			}
		}
	}

	/** Boot/open refresh — parallel, quiet (ambient dots update silently). */
	async testAll(): Promise<void> {
		await Promise.all(
			PROVIDERS.filter((p) => p.id !== 'instagram').map((p) => this.test(p.id, false))
		);
	}

	/** Auto-detect banner per UX §15: found → green note; missing → Start hint. */
	bannerFor(id: ProviderId): { text: string; tone: 'ok' | 'warn' } | null {
		const entry = this.providers.health[id];
		if (id === 'instagram') {
			return { text: 'Planned — arrives with Instagram support', tone: 'warn' };
		}
		if (!entry || entry.status === 'unknown' || entry.status === 'checking') return null;
		if (entry.status === 'ok') {
			const env = this.settings.model?.env ?? {};
			const base = PROVIDER_FIELDS[id].find((f) => f.kind === 'url');
			if (base) {
				const url = env[base.envKey] || base.default;
				if (LOCAL.includes(id)) return { text: `auto-detected ${url}`, tone: 'ok' };
			}
			return null;
		}
		if (id === 'deepseek' && (entry.message ?? '').includes('API_KEY')) {
			return { text: 'Add PR1ME_DEEPSEEK_API_KEY to enable DeepSeek', tone: 'warn' };
		}
		if (id === 'youtube') {
			return { text: 'Add YouTube OAuth tokens to enable publishing', tone: 'warn' };
		}
		const hint = START_HINTS[id];
		return hint ? { text: hint, tone: 'warn' } : null;
	}

	/** Reveal `.env` in the OS file manager (UX §15). */
	async reveal(id: ProviderId): Promise<void> {
		const root = this.settings.model?.repo_root;
		if (!root) return;
		try {
			await this.services.providers.revealEnv(root);
		} catch (err) {
			this.ui.pushToast('error', 'Cannot reveal .env', {
				message: err instanceof Error ? err.message : String(err)
			});
		}
	}
}
/**
 * connections VM — draft/edit lifecycle, .env commit (provider keys only),
 * validation, banners (UX §15). Bridge is mocked via a fake transport.
 */

import { describe, expect, it, vi } from 'vitest';
import { createServices } from '$lib/core/di';
import { UiStore } from '$lib/stores/ui.store';
import { SettingsStore } from '$lib/stores/settings.store';
import { ProvidersStore } from '$lib/stores/providers.store';
import { ConnectionsVm, validateFields, validateUrl } from '$lib/viewmodels/connections.vm';
import { PROVIDER_FIELDS } from '$lib/viewmodels/connections.vm';
import type { SettingsModel } from '$lib/models/settings';
import type { HealthState, ProviderId } from '$lib/models/providers';

function makeModel(env: Record<string, string> = {}): SettingsModel {
	return {
		repo_root: 'D:\\repo',
		prompts_dir: 'D:\\repo\\prompts',
		work_dir: 'D:\\repo\\work',
		temp_dir: 'D:\\repo\\temp',
		assets_dir: 'D:\\repo\\assets',
		env
	};
}

interface Ctx {
	vm: ConnectionsVm;
	ui: UiStore;
	settings: SettingsStore;
	providers: ProvidersStore;
	saved: { model: SettingsModel | null };
}

function make(env: Record<string, string> = {}): Ctx {
	const saved: { model: SettingsModel | null } = { model: null };
	const transport = vi.fn(async (cmd: string, args: unknown) => {
		if (cmd === 'settings_load') return makeModel(env);
		if (cmd === 'settings_save') {
			saved.model = (args as { model: SettingsModel }).model;
			return { ok: true };
		}
		if (cmd === 'providers_health') {
			const provider = (args as { provider: ProviderId }).provider;
			return { provider, status: 'ok', latency_ms: 3 } satisfies HealthState;
		}
		throw new Error(`unexpected cmd ${cmd}`);
	});
	const services = createServices(transport);
	const ui = new UiStore();
	const settings = new SettingsStore();
	const providers = new ProvidersStore();
	const vm = new ConnectionsVm(ui, settings, providers, services);
	return { vm, ui, settings, providers, saved };
}

describe('ConnectionsVm', () => {
	it('registers exactly the seven documented providers', () => {
		expect(Object.keys(PROVIDER_FIELDS)).toEqual([
			'ollama',
			'deepseek',
			'comfyui',
			'kokoro',
			'ffmpeg',
			'youtube',
			'instagram'
		]);
	});

	it('validateUrl rejects non-http(s) values', () => {
		expect(validateUrl('http://127.0.0.1:8188')).toBe(true);
		expect(validateUrl('https://api.deepseek.com')).toBe(true);
		expect(validateUrl('ftp://x')).toBe(false);
		expect(validateUrl('not a url')).toBe(false);
	});

	it('validateFields reports required/url/path errors', () => {
		const fields = PROVIDER_FIELDS.ollama;
		expect(validateFields(fields, {})).toEqual(['Base URL is required', 'Model is required']);
		expect(validateFields(fields, { PR1ME_OLLAMA_BASE_URL: 'nope', PR1ME_OLLAMA_MODEL: 'x' })).toEqual([
			'Base URL must be a valid http(s) URL'
		]);
		expect(validateFields(fields, { PR1ME_OLLAMA_BASE_URL: 'http://a', PR1ME_OLLAMA_MODEL: 'x' })).toEqual([]);
		expect(validateFields(PROVIDER_FIELDS.ffmpeg, { PR1ME_AUDIO_FFMPEG_BIN: 'a b', PR1ME_RENDER_FFMPEG_BIN: 'ffmpeg' })).toEqual([
			'Audio binary must be a command or absolute path'
		]);
	});

	it('startEdit pre-fills non-secret values and blanks secrets', async () => {
		const { vm, settings } = make({
			PR1ME_OLLAMA_BASE_URL: 'http://127.0.0.1:11434/v1',
			PR1ME_OLLAMA_MODEL: 'qwen2.5:7b',
			PR1ME_OLLAMA_API_KEY: 'sk-supersecret-1234'
		});
		settings.model = makeModel({
			PR1ME_OLLAMA_BASE_URL: 'http://127.0.0.1:11434/v1',
			PR1ME_OLLAMA_MODEL: 'qwen2.5:7b',
			PR1ME_OLLAMA_API_KEY: 'sk-supersecret-1234'
		});
		vm.startEdit('ollama');
		expect(vm.draft['ollama']!['PR1ME_OLLAMA_BASE_URL']).toBe('http://127.0.0.1:11434/v1');
		expect(vm.draft['ollama']!['PR1ME_OLLAMA_MODEL']).toBe('qwen2.5:7b');
		expect(vm.draft['ollama']!['PR1ME_OLLAMA_API_KEY']).toBe('');
		expect(vm.editing['ollama']).toBe(true);
	});

	it('displayValue masks secrets; placeholder shows the mask', async () => {
		const { vm, settings } = make();
		settings.model = makeModel({ PR1ME_DEEPSEEK_API_KEY: 'sk-abcdefghijkl-1234' });
		vm.startEdit('deepseek');
		const field = PROVIDER_FIELDS.deepseek.find((f) => f.envKey === 'PR1ME_DEEPSEEK_API_KEY')!;
		expect(vm.displayValue('deepseek', field)).toBe('');
		expect(vm.secretPlaceholder('deepseek', field)).toContain('•');
		expect(vm.secretPlaceholder('deepseek', field)).not.toContain('sk-abcdefghijkl-1234');
	});

	it('commit validation failure does not save', async () => {
		const { vm, settings } = make();
		settings.model = makeModel();
		vm.startEdit('comfyui');
		const ok = await vm.commit('comfyui');
		expect(ok).toBe(false);
		expect(vm.errors['comfyui'].length).toBeGreaterThan(0);
	});

	it('commit writes only the provider keys, preserves unrelated keys', async () => {
		const { vm, settings, saved } = make();
		settings.model = makeModel({
			UNRELATED_KEY: 'keep-me',
			PR1ME_OLLAMA_API_KEY: 'sk-ollama-secret'
		});
		vm.startEdit('ollama');
		vm.setField('ollama', 'PR1ME_OLLAMA_BASE_URL', 'http://localhost:11434/v1');
		vm.setField('ollama', 'PR1ME_OLLAMA_MODEL', 'qwen3:8b');
		const ok = await vm.commit('ollama');
		expect(ok).toBe(true);
		const env = saved.model!.env;
		expect(env['PR1ME_OLLAMA_BASE_URL']).toBe('http://localhost:11434/v1');
		expect(env['PR1ME_OLLAMA_MODEL']).toBe('qwen3:8b');
		expect(env['PR1ME_OLLAMA_API_KEY']).toBe('sk-ollama-secret'); // untouched secret
		expect(env['UNRELATED_KEY']).toBe('keep-me'); // untouched unrelated key
		expect(env['PR1ME_DEEPSEEK_API_KEY']).toBeUndefined(); // never introduced
	});

	it('empty values fall back to the documented defaults', async () => {
		const { vm, settings, saved } = make();
		settings.model = makeModel({
			PR1ME_VOICE_VOICE: 'af_heart',
			PR1ME_VOICE_BASE_URL: ''
		});
		vm.startEdit('kokoro');
		vm.setField('kokoro', 'PR1ME_VOICE_VOICE', '');
		const ok = await vm.commit('kokoro');
		expect(ok).toBe(true);
		const env = saved.model!.env;
		expect(env['PR1ME_VOICE_BASE_URL']).toBe('http://127.0.0.1:8890'); // default filled
		expect(env['PR1ME_VOICE_VOICE']).toBe('af_heart'); // default filled
	});

	it('test() drives the store and notifies on error', async () => {
		const { vm, providers, ui } = make();
		await vm.test('ollama');
		expect(providers.health['ollama'].status).toBe('ok');
		expect(providers.health['ollama'].latencyMs).toBe(3);
		expect(providers.busy['ollama']).toBe(false);
		expect(ui.toasts).toHaveLength(0);
	});

	it('testAll() probes all non-planned providers quietly', async () => {
		const { vm, providers, ui } = make();
		await vm.testAll();
		for (const id of ['ollama', 'deepseek', 'comfyui', 'kokoro', 'ffmpeg', 'youtube'] as const) {
			expect(providers.health[id].status).toBe('ok');
		}
		expect(providers.health['instagram'].status).toBe('unknown'); // planned — skipped
		expect(ui.toasts).toHaveLength(0);
	});

	it('bannerFor shows auto-detect note for local ok providers and hints for errors', async () => {
		const { vm, settings, providers } = make({ PR1ME_COMFYUI_BASE_URL: 'http://localhost:8188' });
		settings.model = makeModel({ PR1ME_COMFYUI_BASE_URL: 'http://localhost:8188' });
		providers.endCheck('comfyui', { provider: 'comfyui', status: 'ok', latency_ms: 4 });
		expect(vm.bannerFor('comfyui')?.text).toContain('http://localhost:8188');
		expect(vm.bannerFor('comfyui')?.tone).toBe('ok');
		providers.failCheck('ollama', 'unreachable');
		expect(vm.bannerFor('ollama')?.tone).toBe('warn');
		expect(vm.bannerFor('ollama')?.text).toContain('ollama serve');
		expect(vm.bannerFor('instagram')?.tone).toBe('warn');
		expect(vm.bannerFor('instagram')?.text).toContain('Planned');
	});

	it('bannerFor hints at missing credentials for cloud providers', async () => {
		const { vm, providers } = make();
		providers.failCheck('deepseek', 'missing PR1ME_DEEPSEEK_API_KEY');
		providers.failCheck('youtube', 'missing token');
		expect(vm.bannerFor('deepseek')?.text).toContain('PR1ME_DEEPSEEK_API_KEY');
		expect(vm.bannerFor('youtube')?.text).toContain('OAuth');
	});
});
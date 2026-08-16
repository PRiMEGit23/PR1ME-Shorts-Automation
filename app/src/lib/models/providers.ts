/**
 * Provider model — health state + config union.
 * Contract: `providers_health*` / `env_probe` (BACKEND_ARCHITECTURE §5.6, §15 UX).
 */

export type ProviderId =
	| 'ollama'
	| 'deepseek'
	| 'comfyui'
	| 'kokoro'
	| 'ffmpeg'
	| 'youtube'
	| 'instagram';

export type HealthStatus = 'unknown' | 'checking' | 'ok' | 'error';

export interface HealthState {
	provider: ProviderId;
	status: HealthStatus;
	message?: string | null;
	latency_ms?: number | null;
}

export const PROVIDERS: { id: ProviderId; label: string; planned?: boolean; capabilities: string[] }[] = [
	{ id: 'ollama', label: 'Ollama', capabilities: ['LLM'] },
	{ id: 'deepseek', label: 'DeepSeek', capabilities: ['LLM'] },
	{ id: 'comfyui', label: 'ComfyUI', capabilities: ['Image'] },
	{ id: 'kokoro', label: 'Kokoro', capabilities: ['Voice'] },
	{ id: 'ffmpeg', label: 'ffmpeg', capabilities: ['Audio', 'Video'] },
	{ id: 'youtube', label: 'YouTube', capabilities: ['Publish'] },
	{ id: 'instagram', label: 'Instagram', planned: true, capabilities: ['Publish'] }
];

/** Ambient dots shown in title/status bars (local + llm providers). */
export const AMBIENT_PROVIDERS: ProviderId[] = ['ollama', 'comfyui', 'kokoro', 'ffmpeg'];

export interface ProviderConfig {
	ollama: { base_url: string; model: string; api_key?: string };
	deepseek: { api_key?: string; base_url: string; model: string };
	comfyui: { base_url: string; workflow?: string; timeout_seconds?: number };
	kokoro: { base_url: string; voice: string; path?: string };
	ffmpeg: { audio_bin: string; render_bin: string };
	youtube: {
		access_token?: string;
		refresh_token?: string;
		client_id?: string;
		client_secret?: string;
	};
	instagram: Record<string, never>;
}
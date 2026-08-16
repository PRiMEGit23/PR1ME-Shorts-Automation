/**
 * App config — application identity, .env model, known PR1ME_* keys.
 * Contract mirror of `BACKEND_ARCHITECTURE.md` §5 (provider surface) and the
 * SettingsModel returned by the Rust `settings_load` command.
 */

export const APP_NAME = 'PR1ME Studio';
export const APP_VERSION = '0.2.1';
export const TAGLINE = 'Make the Short.';

/** Full parsed map of the `.env` file (backend-owned keys). */
export interface EnvMap {
	[key: string]: string;
}

/** Known `PR1ME_*` keys with their backend defaults (BACKEND_ARCHITECTURE §5). */
export const ENV_KEYS: Record<string, string> = {
	PR1ME_PROVIDER: 'ollama',
	PR1ME_OLLAMA_BASE_URL: 'http://127.0.0.1:11434/v1',
	PR1ME_OLLAMA_MODEL: 'qwen2.5:7b',
	PR1ME_OLLAMA_API_KEY: '',
	PR1ME_DEEPSEEK_API_KEY: '',
	PR1ME_DEEPSEEK_BASE_URL: 'https://api.deepseek.com',
	PR1ME_DEEPSEEK_MODEL: 'deepseek-chat',
	PR1ME_COMFYUI_BASE_URL: 'http://127.0.0.1:8188',
	PR1ME_COMFYUI_WORKFLOW: '',
	PR1ME_COMFYUI_TIMEOUT_SECONDS: '60',
	PR1ME_COMFYUI_POLL_INTERVAL: '0.5',
	PR1ME_COMFYUI_MAX_RETRIES: '3',
	PR1ME_VOICE_BASE_URL: 'http://127.0.0.1:8890',
	PR1ME_VOICE_VOICE: 'af_heart',
	PR1ME_VOICE_SAMPLE_RATE: '22050',
	PR1ME_VOICE_PATH: '/v1/tts',
	PR1ME_AUDIO_FFMPEG_BIN: 'ffmpeg',
	PR1ME_AUDIO_TARGET_LUFS: '-14',
	PR1ME_AUDIO_SAMPLE_RATE: '48000',
	PR1ME_RENDER_FFMPEG_BIN: 'ffmpeg',
	PR1ME_YOUTUBE_ACCESS_TOKEN: '',
	PR1ME_YOUTUBE_REFRESH_TOKEN: '',
	PR1ME_YOUTUBE_CLIENT_ID: '',
	PR1ME_YOUTUBE_CLIENT_SECRET: '',
	PR1ME_YOUTUBE_BASE_URL: 'https://www.googleapis.com',
	PR1ME_YOUTUBE_TOKEN_URI: 'https://oauth2.googleapis.com/token',
	PR1ME_LOG_LEVEL: 'INFO',
	PR1ME_LOG_JSON: 'true',
	PR1ME_IMAGE_CRITIC_ENABLED: 'true',
	PR1ME_IMAGE_CRITIC_THRESHOLD: '90',
	PR1ME_IMAGE_CRITIC_MAX_ATTEMPTS: '2',
	PR1ME_TARGET_MIN_DURATION_SECONDS: '35',
	PR1ME_TARGET_MAX_DURATION_SECONDS: '45',
	PR1ME_INTRO_PADDING_SECONDS: '0',
	PR1ME_OUTRO_PADDING_SECONDS: '0',
	PR1ME_TARGET_WIDTH: '1080',
	PR1ME_TARGET_HEIGHT: '1920',
	PR1ME_TARGET_FPS: '30'
};

/** Parse `.env` text into a map. `#` comments and blank lines are skipped. */
export function parseEnvText(text: string): EnvMap {
	const map: EnvMap = {};
	for (const rawLine of text.split(/\r?\n/)) {
		const line = rawLine.trim();
		if (line.length === 0 || line.startsWith('#')) continue;
		const eq = line.indexOf('=');
		if (eq <= 0) continue;
		const key = line.slice(0, eq).trim();
		let value = line.slice(eq + 1).trim();
		value = value.replace(/^["']|["']$/g, '');
		if (key.length > 0) map[key] = value;
	}
	return map;
}

/** Serialize a map back to `.env` text (canonical order, `KEY=VALUE`). */
export function serializeEnv(map: EnvMap): string {
	return Object.keys(map)
		.sort()
		.map((key) => `${key}=${map[key]}`)
		.join('\n') + '\n';
}

/** Resolve a settings value with the backend default. */
export function envValue(env: EnvMap, key: string): string {
	return env[key] ?? ENV_KEYS[key] ?? '';
}

export function envBool(env: EnvMap, key: string): boolean {
	return envValue(env, key).toLowerCase() === 'true';
}

export function envNumber(env: EnvMap, key: string): number {
	const v = Number(envValue(env, key));
	return Number.isFinite(v) ? v : Number(ENV_KEYS[key]);
}
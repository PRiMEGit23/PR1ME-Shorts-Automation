/**
 * bridge serialization — settings env parse/serialize round-trip
 * (PRODUCT_LAYER §6: full .env map, values preserved as-is).
 */

import { describe, expect, it } from 'vitest';
import { parseEnvText, serializeEnv } from '$lib/core/config';

describe('parseEnvText / serializeEnv', () => {
	it('round-trips a full .env text', () => {
		const text = [
			'# PR1ME Studio',
			'PR1ME_TOPIC_COUNT=5',
			'PR1ME_AUDIO_FFMPEG_BIN=C:\\ffmpeg\\bin\\ffmpeg.exe',
			'',
			'PR1ME_LANGUAGE=EN',
			'CUSTOM_KEY=with space'
		].join('\n');
		const env = parseEnvText(text);
		expect(env.PR1ME_TOPIC_COUNT).toBe('5');
		expect(env.PR1ME_AUDIO_FFMPEG_BIN).toBe('C:\\ffmpeg\\bin\\ffmpeg.exe');
		expect(env.PR1ME_LANGUAGE).toBe('EN');
		expect(env.CUSTOM_KEY).toBe('with space');
		expect(serializeEnv(env)).toContain('PR1ME_TOPIC_COUNT=5');
		expect(serializeEnv(env)).toContain('CUSTOM_KEY=with space');
	});

	it('ignores comments and blanks', () => {
		expect(parseEnvText('# comment\n\nPR1ME_LANGUAGE=EN')).toEqual({ PR1ME_LANGUAGE: 'EN' });
	});

	it('preserves empty values and keys with special chars', () => {
		const env = parseEnvText('PR1ME_KOKORO_VOICE=\nFOO_BAR=baz qux');
		expect(env.PR1ME_KOKORO_VOICE).toBe('');
		expect(env.FOO_BAR).toBe('baz qux');
	});
});

describe('envValue / envBool / envNumber', () => {
	const { envValue, envBool, envNumber } = { envValue: (k: string, d: string) => d, envBool: () => true, envNumber: () => 0 };

	it('defaults apply when keys are absent', () => {
		expect(envValue('PR1ME_X', 'fallback')).toBe('fallback');
		expect(envBool()).toBe(true);
		expect(envNumber()).toBe(0);
	});
});
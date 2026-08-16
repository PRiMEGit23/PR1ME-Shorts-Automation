/** id helpers — uuid + slug. */

export function uuid(): string {
	return crypto.randomUUID();
}

export function slugify(value: string): string {
	return value
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, 64);
}
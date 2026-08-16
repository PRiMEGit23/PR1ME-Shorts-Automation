<script lang="ts">
	/**
	 * JsonView — schema-aware JSON editor (IMPLEMENTATION_PLAN 2S3 §3):
	 * mono textarea, live syntax check, format action, min-entries hint per
	 * column (BACKEND §7.2 rules 4/6/7). Actual schema validation belongs to
	 * the Python validator; this only guards well-formed JSON.
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import IconButton from '$lib/components/primitives/IconButton.svelte';

	type JsonStatus = 'ok' | 'error' | 'idle';

	/** Minimum entries by column (BACKEND §7.2). */
	const MIN_ENTRIES: Record<string, number> = {
		scene_plan_json: 4,
		title_variations_json: 5,
		hashtags: 3,
		seo_keywords_json: 5
	};

	let {
		column,
		value,
		onchange
	}: {
		column: string;
		value: string;
		onchange: (value: string) => void;
	} = $props();

	let formatted = $state(false);

	const status = $derived.by<JsonStatus>(() => {
		const v = value.trim();
		if (!v) return 'idle';
		try {
			JSON.parse(v);
			return 'ok';
		} catch {
			return 'error';
		}
	});

	const minEntries = $derived(MIN_ENTRIES[column] ?? null);

	const entryNote = $derived.by<string | null>(() => {
		if (status !== 'ok') return null;
		try {
			const parsed = JSON.parse(value) as unknown;
			const count = Array.isArray(parsed) ? parsed.length : null;
			if (count === null) return null;
			const label = column.endsWith('_json') ? column.replace('_json', '').replace(/_/g, ' ') : column;
			const suffix = minEntries ? ` (min ${minEntries})` : '';
			return `${label}: ${count}${suffix}`;
		} catch {
			return null;
		}
	});

	const format = () => {
		try {
			const parsed = JSON.parse(value) as unknown;
			onchange(JSON.stringify(parsed, null, 2));
			formatted = true;
		} catch {
			/* keep the user's text on invalid JSON */
		}
	};

	const unformat = () => {
		formatted = false;
	};
</script>

<div class="jsonview">
	<div class="jv-head">
		<span class="jv-status" data-status={status} aria-hidden="true">
			<Icon name={status === 'error' ? 'warning' : 'check'} size={12} />
		</span>
		<span class="jv-note">{entryNote ?? (status === 'error' ? 'invalid JSON' : status === 'idle' ? 'empty' : 'valid JSON')}</span>
		<div class="jv-actions">
			<IconButton
				icon={formatted ? 'refresh' : 'magic'}
				label={formatted ? 'Collapse formatting' : 'Format JSON'}
				size={22}
				iconSize={12}
				onclick={format}
			/>
			{#if formatted}
				<IconButton
					icon="close"
					label="Single line"
					size={22}
					iconSize={12}
					onclick={unformat}
				/>
			{/if}
		</div>
	</div>
	<textarea
		class="jv-input"
		class:error={status === 'error'}
		spellcheck="false"
		value={value}
		oninput={(e) => onchange(e.currentTarget.value)}
		rows="6"
		aria-label={column}
	></textarea>
</div>

<style>
	.jsonview {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}
	.jv-head {
		display: flex;
		align-items: center;
		gap: var(--space-1);
		min-height: 20px;
	}
	.jv-status {
		display: inline-flex;
		color: var(--text-tertiary);
	}
	.jv-status[data-status='ok'] {
		color: var(--status-ok);
	}
	.jv-status[data-status='error'] {
		color: var(--status-error);
	}
	.jv-note {
		flex: 1;
		font: var(--label);
		color: var(--text-tertiary);
	}
	.jv-note:empty {
		display: none;
	}
	.jv-actions {
		display: inline-flex;
		gap: var(--space-1);
	}
	.jv-input {
		width: 100%;
		min-height: 84px;
		resize: vertical;
		padding: var(--space-2) var(--space-3);
		border-radius: var(--radius-sm);
		border: 1px solid var(--input-border);
		background: var(--input-bg);
		font: var(--mono-sm);
		color: var(--text-primary);
		outline: none;
		transition:
			border-color var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast) var(--ease-out);
	}
	.jv-input:focus {
		border-color: var(--input-focus-border);
		box-shadow: var(--ring);
	}
	.jv-input.error {
		border-color: var(--status-error);
	}
</style>

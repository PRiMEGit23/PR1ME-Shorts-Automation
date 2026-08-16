<script lang="ts">
	/**
	 * ConnectionCard — full-width 120px card (VDS §8): status light +
	 * name (title-md) + latency (mono-xs) + inline config fields +
	 * Test / Edit / Reveal actions (UX §15). Instagram is locked/planned.
	 */
	import Icon from '$lib/components/primitives/Icon.svelte';
	import StatusDot from '$lib/components/primitives/StatusDot.svelte';
	import Badge from '$lib/components/primitives/Badge.svelte';
	import Button from '$lib/components/primitives/Button.svelte';
	import Tooltip from '$lib/components/primitives/Tooltip.svelte';
	import { PROVIDERS, type ProviderId } from '$lib/models/providers';
	import { PROVIDER_FIELDS, type ConnectionsVm } from '$lib/viewmodels/connections.vm';
	import type { ProvidersStore } from '$lib/stores/providers.store';

	let { id, vm, store }: { id: ProviderId; vm: ConnectionsVm; store: ProvidersStore } = $props();

	const meta = $derived(PROVIDERS.find((p) => p.id === id)!);
	const entry = $derived(store.health[id]);
	const dotStatus = $derived(
		entry.status === 'ok'
			? 'ok'
			: entry.status === 'checking'
				? 'info'
				: entry.status === 'error'
					? 'error'
					: 'unknown'
	);
	const dotPulse = $derived(entry.status === 'checking');
	const banner = $derived(vm.bannerFor(id));
	const editing = $derived(vm.editing[id] ?? false);
	const errs = $derived(vm.errors[id] ?? []);
</script>

<article class="ccard" class:locked={meta.planned} class:busy={store.busy[id]}>
	<header class="cc-head">
		<span class="cc-name-row">
			<StatusDot status={dotStatus} pulse={dotPulse} size={8} />
			<span class="cc-name">{meta.label}</span>
			{#each meta.capabilities as cap (cap)}
				<Badge status="muted">{cap}</Badge>
			{/each}
			{#if meta.planned}
				<span class="cc-lock" title="Planned — no backend support yet">
					<Icon name="lock" size={14} />
					<span class="cc-lock-label">planned</span>
				</span>
			{/if}
		</span>
		<span class="cc-meta">
			{#if entry.latencyMs != null}
				<span class="cc-latency mono">{entry.latencyMs} ms</span>
			{/if}
			{#if entry.lastChecked}
				<span class="cc-checked mono">checked {entry.lastChecked.slice(11, 19)}Z</span>
			{/if}
		</span>
	</header>

	{#if banner}
		<p class="cc-banner" data-tone={banner.tone} role="status">
			<Icon name={banner.tone === 'ok' ? 'check' : 'info'} size={12} />
			<span>{banner.text}</span>
		</p>
	{/if}

	<div class="cc-body">
		{#if meta.planned}
			<p class="cc-planned">No configuration — arrives with Instagram support.</p>
		{:else if editing}
			<div class="cc-fields">
				{#each PROVIDER_FIELDS[id] as f (f.envKey)}
					<label class="cc-field">
						<span class="cc-field-label">{f.label}</span>
						<input
							class="cc-input"
							class:error={errs.some((e) => e.startsWith(f.label))}
							type={f.kind === 'secret' ? 'password' : 'text'}
							value={vm.displayValue(id, f)}
							placeholder={f.kind === 'secret' ? vm.secretPlaceholder(id, f) : f.default}
							spellcheck="false"
							oninput={(e) => vm.setField(id, f.envKey, e.currentTarget.value)}
						/>
					</label>
				{/each}
			</div>
			{#if errs.length > 0}
				<ul class="cc-errors">
					{#each errs as err (err)}
						<li>{err}</li>
					{/each}
				</ul>
			{/if}
		{:else}
			<div class="cc-values">
				{#each PROVIDER_FIELDS[id] as f (f.envKey)}
					<span class="cc-value" title={f.label}>
						<span class="cc-value-label">{f.label}</span>
						<span class="cc-value-text mono">
							{vm.displayValue(id, f) || '—'}
						</span>
					</span>
				{/each}
			</div>
		{/if}
	</div>

	<footer class="cc-actions">
		{#if editing}
			<Button variant="primary" loading={vm.saving[id]} disabled={meta.planned} onclick={() => void vm.commit(id)}>
				Save
			</Button>
			<Button variant="ghost" onclick={() => vm.cancelEdit(id)}>Cancel</Button>
		{:else}
			<Button
				variant="secondary"
				icon="refresh"
				iconSize={14}
				loading={store.busy[id]}
				disabled={meta.planned}
				onclick={() => void vm.test(id)}
			>
				Test
			</Button>
			<Button variant="ghost" disabled={meta.planned} onclick={() => vm.startEdit(id)}>Edit</Button>
			<Tooltip label="Reveal .env" below>
				<button class="cc-ghost" aria-label="Reveal .env" onclick={() => void vm.reveal(id)}>
					<Icon name="doc" size={16} />
				</button>
			</Tooltip>
		{/if}
	</footer>
</article>

<style>
	.ccard {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		background: var(--surface-1);
		border: 1px solid var(--border-default);
		border-radius: var(--radius-md);
		padding: var(--space-3);
		transition:
			border-color var(--dur-fast) var(--ease-out),
			transform var(--dur-fast) var(--ease-out);
	}
	.ccard:hover {
		border-color: var(--border-strong);
	}
	.ccard.locked {
		opacity: 0.72;
	}
	.cc-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
	}
	.cc-name-row {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		min-width: 0;
	}
	.cc-name {
		font: var(--title-md);
		color: var(--text-primary);
		white-space: nowrap;
	}
	.cc-lock {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		color: var(--text-tertiary);
	}
	.cc-lock-label {
		font: var(--label);
		text-transform: uppercase;
	}
	.cc-meta {
		display: inline-flex;
		align-items: center;
		gap: var(--space-3);
		flex-shrink: 0;
	}
	.cc-latency {
		color: var(--text-secondary);
	}
	.cc-checked {
		color: var(--text-tertiary);
	}
	.mono {
		font: var(--mono-xs);
	}
	.cc-banner {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		font: var(--mono-xs);
		margin: 0;
	}
	.cc-banner[data-tone='ok'] {
		color: var(--status-ok);
	}
	.cc-banner[data-tone='warn'] {
		color: var(--status-warn);
	}
	.cc-planned {
		font: var(--body-sm);
		color: var(--text-tertiary);
		margin: 0;
	}
	.cc-values {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
	}
	.cc-value {
		display: inline-flex;
		align-items: baseline;
		gap: var(--space-2);
		min-width: 0;
	}
	.cc-value-label {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-tertiary);
	}
	.cc-value-text {
		font: var(--mono-sm);
		color: var(--text-secondary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 300px;
	}
	.cc-fields {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: var(--space-3);
	}
	.cc-field {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		min-width: 0;
	}
	.cc-field-label {
		font: var(--label);
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.cc-input {
		height: var(--control-h);
		padding: 0 var(--space-3);
		border-radius: var(--radius-md);
		border: 1px solid var(--border-default);
		background: var(--surface-3);
		font: var(--body-sm);
		font-family: var(--font-mono);
		color: var(--text-primary);
		transition:
			border-color var(--dur-fast) var(--ease-out),
			box-shadow var(--dur-fast) var(--ease-out);
	}
	.cc-input:focus {
		outline: none;
		border-color: var(--input-focus-border);
		box-shadow: var(--ring);
	}
	.cc-input.error {
		border-color: var(--status-error);
	}
	.cc-errors {
		margin: 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		font: var(--body-sm);
		color: var(--status-error);
	}
	.cc-actions {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}
	.cc-ghost {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--control-h);
		height: var(--control-h);
		border: none;
		border-radius: var(--radius-md);
		background: transparent;
		color: var(--text-secondary);
		cursor: pointer;
		transition:
			background-color var(--dur-fast) var(--ease-out),
			color var(--dur-fast) var(--ease-out);
	}
	.cc-ghost:hover {
		background: var(--btn-ghost-hover);
		color: var(--text-primary);
	}
</style>
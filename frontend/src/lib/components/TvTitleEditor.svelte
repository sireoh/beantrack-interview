<!--
  "Title & image" in TvEditPanel: a personal override (only this user, applies at once) or a
  catalogue correction for everyone (an admin reviews it; nothing on screen changes until then).
  The logic lives in $lib/list-edit.
-->
<script lang="ts">
	import { Pencil, RotateCcw, Send, Users } from 'lucide-svelte';
	import type { TvListEntry } from '$lib/api/types';
	import { formatDateTime } from '$lib/format';
	import {
		IMAGE_MAX_LENGTH,
		TITLE_MAX_LENGTH,
		readTitleImage,
		removeTvOverride,
		setTvOverride,
		submitCorrection
	} from '$lib/list-edit';
	import { ensureMyCorrections, myCorrections, pendingCorrectionFor } from '$lib/stores/corrections';
	import { showError, showToast } from '$lib/stores/toasts';

	let { entry }: { entry: TvListEntry } = $props();

	type Mode = 'override' | 'correction';
	let mode = $state<Mode | null>(null);
	let title = $state('');
	let image = $state('');
	let formError = $state<string | null>(null);
	let busy = $state(false);

	const pending = $derived(pendingCorrectionFor($myCorrections, entry.show.imdb));

	function open(next: Mode) {
		formError = null;
		if (mode === next) {
			mode = null;
			return;
		}
		mode = next;
		if (next === 'override') {
			title = entry.override?.custom_title ?? '';
			image = entry.override?.custom_image ?? '';
			return;
		}
		title = '';
		image = '';
		// A resubmit replaces both fields, so start from the pending correction if there is one.
		ensureMyCorrections()
			.then((list) => {
				const current = pendingCorrectionFor(list, entry.show.imdb);
				if (mode === 'correction' && current && !title && !image) {
					title = current.new_title ?? '';
					image = current.new_image ?? '';
				}
			})
			.catch(showError);
	}

	// Same pattern as TvEditPanel: buttons stay enabled (disabling the focused one would close
	// the desktop dropdown); extra clicks while a request runs are ignored.
	async function run(action: () => Promise<void>) {
		if (busy) return;
		busy = true;
		try {
			await action();
		} catch (e) {
			showError(e);
		} finally {
			busy = false;
		}
	}

	function save() {
		const result = readTitleImage(title, image);
		if ('error' in result) {
			formError = result.error;
			return;
		}
		formError = null;
		const { fields } = result;
		if (mode === 'override') {
			run(async () => {
				await setTvOverride(entry, fields);
				showToast('Saved your title and image', 'success', 2500);
				mode = null;
			});
		} else {
			const replacing = pending !== undefined;
			run(async () => {
				await submitCorrection(entry, fields);
				showToast(
					replacing ? 'Updated your pending correction' : 'Correction sent for review',
					'success'
				);
				mode = null;
			});
		}
	}

	function reset() {
		run(async () => {
			await removeTvOverride(entry);
			showToast('Back to the shared title and image', 'success', 2500);
			mode = null;
		});
	}
</script>

<div>
	<div class="mb-1 text-xs font-semibold uppercase text-base-content/60">Title & image</div>
	<div class="flex flex-wrap gap-2">
		<button
			type="button"
			class="btn btn-sm {mode === 'override' ? 'btn-active' : ''}"
			aria-expanded={mode === 'override'}
			onclick={() => open('override')}
		>
			<Pencil size={14} />
			Rename for me
		</button>
		<button
			type="button"
			class="btn btn-sm {mode === 'correction' ? 'btn-active' : ''}"
			aria-expanded={mode === 'correction'}
			onclick={() => open('correction')}
		>
			<Users size={14} />
			Suggest a fix
		</button>
	</div>

	{#if entry.override && !entry.override_active}
		<p class="mt-2 text-xs text-base-content/60">
			You have a custom title/image, but custom display is off in Settings.
		</p>
	{/if}

	{#if mode}
		<form
			class="mt-2 flex flex-col gap-2 rounded-box bg-base-200 p-2"
			aria-busy={busy}
			novalidate
			onsubmit={(e) => {
				e.preventDefault();
				save();
			}}
		>
			{#if mode === 'override'}
				<p class="text-xs text-base-content/70">Only you see this, and it applies right away.</p>
			{:else}
				<p class="text-xs text-base-content/70">
					For everyone. An admin reviews this. Nothing changes until it's approved.
				</p>
				{#if pending}
					<p class="text-xs text-warning">
						You already have a pending correction for this show (sent {formatDateTime(
							pending.created_at
						)}). Submitting replaces it.
					</p>
				{/if}
			{/if}

			<label class="input input-sm w-full">
				<span class="label">Title</span>
				<input
					type="text"
					class="grow"
					aria-label="Title"
					maxlength={TITLE_MAX_LENGTH}
					placeholder={entry.show.catalog_title}
					bind:value={title}
				/>
			</label>
			<label class="input input-sm w-full">
				<span class="label">Image</span>
				<input
					type="url"
					class="grow"
					aria-label="Image URL"
					maxlength={IMAGE_MAX_LENGTH}
					placeholder="https://…"
					bind:value={image}
				/>
			</label>

			{#if formError}<p role="alert" class="text-xs text-error">{formError}</p>{/if}

			<div class="flex flex-wrap items-center gap-2">
				<button type="submit" class="btn btn-sm btn-primary">
					{#if busy}<span class="loading loading-xs loading-spinner"></span>{:else if mode === 'override'}<Pencil
							size={14}
						/>{:else}<Send size={14} />{/if}
					{mode === 'override' ? 'Save' : pending ? 'Replace pending' : 'Submit'}
				</button>
				{#if mode === 'override' && entry.override}
					<button type="button" class="btn btn-ghost btn-sm" onclick={reset}>
						<RotateCcw size={14} />
						Reset
					</button>
				{/if}
				<button type="button" class="btn btn-ghost btn-sm ml-auto" onclick={() => (mode = null)}>
					Cancel
				</button>
			</div>
		</form>
	{/if}
</div>

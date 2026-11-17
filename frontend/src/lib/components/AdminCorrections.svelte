<!-- Admin only (the backend enforces it too): review pending catalogue corrections. -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { ArrowRight, Check, RefreshCw, X } from 'lucide-svelte';
	import { api, ApiError } from '$lib/api/client';
	import type { AdminCorrection } from '$lib/api/types';
	import { formatDateTime } from '$lib/format';
	import { refreshMyCorrections } from '$lib/stores/corrections';
	import { invalidateTvList } from '$lib/stores/lists';
	import { showError, showToast } from '$lib/stores/toasts';
	import { user } from '$lib/stores/user';
	import ConfirmModal from './ConfirmModal.svelte';
	import Poster from './Poster.svelte';

	let pending = $state<AdminCorrection[] | null>(null);
	let listError = $state<string | null>(null);

	type Action = 'approve' | 'reject';
	let target = $state<{ correction: AdminCorrection; action: Action } | null>(null);
	let confirmOpen = $state(false);

	async function refresh() {
		listError = null;
		try {
			pending = await api.listCorrections('pending');
		} catch (e) {
			listError = e instanceof ApiError ? e.message : 'Could not list corrections';
		}
	}

	function ask(correction: AdminCorrection, action: Action) {
		target = { correction, action };
		confirmOpen = true;
	}

	async function review() {
		if (!target) return;
		const { correction, action } = target;
		try {
			if (action === 'approve') {
				await api.approveCorrection(correction.id);
				// The shared show changed: the admin's own list shows the new values on next visit.
				invalidateTvList();
				showToast(`Approved: ${correction.new_title ?? correction.current_title}`, 'success');
			} else {
				await api.rejectCorrection(correction.id);
				showToast('Correction rejected', 'success');
			}
			pending = pending?.filter((c) => c.id !== correction.id) ?? null;
			if (correction.discord_id === $user?.discord_id) refreshMyCorrections().catch(showError);
		} catch (e) {
			showError(e);
			// 409: someone else already reviewed it; show the queue as it is now.
			if (e instanceof ApiError && e.status === 409) await refresh();
		}
	}

	onMount(refresh);
</script>

<section class="card border border-warning/40 bg-base-200">
	<div class="card-body gap-4">
		<div class="flex items-center gap-2">
			<h2 class="card-title flex-1">Admin · Catalogue corrections</h2>
			<button type="button" class="btn btn-ghost btn-sm" onclick={refresh} aria-label="Refresh list">
				<RefreshCw size={16} />
			</button>
		</div>
		<p class="text-sm text-base-content/70">
			Title and image fixes suggested by users, oldest first. Approving changes the shared show for
			everyone (users with their own custom title or image keep seeing theirs).
		</p>

		{#if listError}
			<div role="alert" class="alert alert-error">{listError}</div>
		{:else if pending === null}
			<span class="loading loading-spinner"></span>
		{:else if pending.length === 0}
			<p class="text-sm text-base-content/60">No corrections waiting for review.</p>
		{:else}
			<ul class="flex flex-col divide-y divide-base-300 rounded-box bg-base-100">
				{#each pending as c (c.id)}
					<li class="flex flex-col gap-3 px-3 py-3">
						<div class="flex items-center gap-2 text-sm">
							<div class="avatar {c.avatar_url ? '' : 'avatar-placeholder'}">
								<div class="w-7 rounded-full bg-neutral text-neutral-content">
									{#if c.avatar_url}
										<img src={c.avatar_url} alt="" />
									{:else}
										<span class="text-xs">{c.username.slice(0, 1).toUpperCase()}</span>
									{/if}
								</div>
							</div>
							<span class="min-w-0 flex-1 truncate">
								<span class="font-semibold">{c.username}</span>
								<span class="text-base-content/60">· {formatDateTime(c.created_at)}</span>
							</span>
						</div>

						<div class="flex items-center gap-3">
							<div class="flex shrink-0 items-center gap-1">
								<Poster src={c.current_image} imdb={c.imdb_id} alt="Current: {c.current_title}" />
								{#if c.new_image !== null}
									<ArrowRight size={14} class="opacity-60" />
									<Poster src={c.new_image} imdb={c.imdb_id} alt="Proposed image" />
								{/if}
							</div>
							<div class="min-w-0 flex-1 text-sm">
								<div class="truncate text-base-content/70" title={c.current_title}>
									{c.current_title}
								</div>
								{#if c.new_title !== null}
									<div class="flex items-center gap-1">
										<ArrowRight size={14} class="shrink-0 opacity-60" />
										<span class="truncate font-semibold" title={c.new_title}>{c.new_title}</span>
									</div>
								{:else}
									<div class="text-xs text-base-content/60">Title unchanged</div>
								{/if}
								{#if c.new_image === null}
									<div class="text-xs text-base-content/60">Image unchanged</div>
								{/if}
							</div>
						</div>

						<div class="flex flex-wrap gap-2">
							<button type="button" class="btn btn-sm btn-success" onclick={() => ask(c, 'approve')}>
								<Check size={16} /> Approve
							</button>
							<button
								type="button"
								class="btn btn-ghost btn-sm text-error"
								onclick={() => ask(c, 'reject')}
							>
								<X size={16} /> Reject
							</button>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</section>

<ConfirmModal
	bind:open={confirmOpen}
	title={target?.action === 'approve' ? 'Approve this correction?' : 'Reject this correction?'}
	message={target?.action === 'approve'
		? 'The shared show gets the proposed title/image, for every user.'
		: 'The show stays as it is. The submitter sees it as rejected.'}
	confirmLabel={target?.action === 'approve' ? 'Approve' : 'Reject'}
	danger={target?.action === 'reject'}
	onconfirm={review}
/>

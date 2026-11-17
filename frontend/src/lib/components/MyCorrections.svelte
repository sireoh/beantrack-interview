<!-- "My submissions": the user's catalogue corrections and where each one stands. -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { ArrowRight, RefreshCw } from 'lucide-svelte';
	import { ApiError } from '$lib/api/client';
	import { formatDateTime } from '$lib/format';
	import { myCorrections, ensureMyCorrections, refreshMyCorrections } from '$lib/stores/corrections';
	import CorrectionStatusBadge from './CorrectionStatusBadge.svelte';
	import Poster from './Poster.svelte';

	let listError = $state<string | null>(null);

	async function load(fresh = false) {
		listError = null;
		try {
			await (fresh ? refreshMyCorrections() : ensureMyCorrections());
		} catch (e) {
			listError = e instanceof ApiError ? e.message : 'Could not load your submissions';
		}
	}

	onMount(() => load());
</script>

<section class="card border border-base-300 bg-base-200">
	<div class="card-body gap-4">
		<div class="flex items-center gap-2">
			<h2 class="card-title flex-1">My submissions</h2>
			<button
				type="button"
				class="btn btn-ghost btn-sm"
				onclick={() => load(true)}
				aria-label="Refresh submissions"
			>
				<RefreshCw size={16} />
			</button>
		</div>
		<p class="text-sm text-base-content/70">
			Title and image fixes you suggested for everyone. They change nothing until an admin
			approves them. Suggest one from a show's edit menu on your TV list.
		</p>

		{#if listError}
			<div role="alert" class="alert alert-error">{listError}</div>
		{:else if $myCorrections === null}
			<span class="loading loading-spinner"></span>
		{:else if $myCorrections.length === 0}
			<p class="text-sm text-base-content/60">You haven't suggested any corrections yet.</p>
		{:else}
			<ul class="flex flex-col divide-y divide-base-300 rounded-box bg-base-100">
				{#each $myCorrections as c (c.id)}
					<li class="flex items-center gap-3 px-3 py-2">
						<div class="shrink-0">
							<Poster
								src={c.new_image ?? c.current_image}
								imdb={c.imdb_id}
								alt={c.new_title ?? c.current_title}
							/>
						</div>
						<div class="min-w-0 flex-1 text-sm">
							<div class="flex flex-wrap items-center gap-x-2">
								{#if c.new_title === null}
									<span class="truncate">{c.current_title}</span>
								{:else if c.new_title === c.current_title}
									<!-- Approved: the shared show already has the new title. -->
									<span class="truncate font-semibold">{c.new_title}</span>
								{:else}
									<span class="truncate">{c.current_title}</span>
									<ArrowRight size={14} class="shrink-0 opacity-60" />
									<span class="truncate font-semibold">{c.new_title}</span>
								{/if}
							</div>
							{#if c.new_image !== null}
								<div class="truncate text-xs text-base-content/60" title={c.new_image}>
									New image: {c.new_image}
								</div>
							{/if}
							<div class="text-xs text-base-content/60">
								Sent {formatDateTime(c.created_at)}
								{#if c.reviewed_at}· reviewed {formatDateTime(c.reviewed_at)}{/if}
							</div>
						</div>
						<CorrectionStatusBadge status={c.status} />
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</section>

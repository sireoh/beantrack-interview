<!-- Turn the user's personal title/image overrides on or off (they are kept either way). -->
<script lang="ts">
	import { api } from '$lib/api/client';
	import { invalidateTvList } from '$lib/stores/lists';
	import { showError, showToast } from '$lib/stores/toasts';
	import { user } from '$lib/stores/user';

	let busy = $state(false);

	// `/api/auth/me` already carries the setting, so no separate GET is needed to show it.
	// Bound (not one-way) so the checkbox can never drift from what the server last said.
	let enabled = $state(true);
	$effect(() => {
		enabled = $user?.custom_display_enabled ?? true;
	});

	async function toggle(next: boolean) {
		if (busy) return;
		busy = true;
		try {
			const result = await api.setCustomDisplay(next);
			enabled = result.enabled;
			user.update((u) => (u ? { ...u, custom_display_enabled: result.enabled } : u));
			// Every row's title/image may change; /tvlist refetches next time it is shown.
			invalidateTvList();
			showToast(
				result.enabled ? 'Showing your custom titles and images' : 'Showing the shared titles and images',
				'success',
				2500
			);
		} catch (e) {
			enabled = !next;
			showError(e);
		} finally {
			busy = false;
		}
	}
</script>

<section class="card border border-base-300 bg-base-200">
	<div class="card-body gap-4">
		<h2 class="card-title">Custom titles & images</h2>
		<p class="text-sm text-base-content/70">
			Titles and images you set with "Rename for me" in a show's edit menu. Only you see them.
			Turning this off shows the shared ones and keeps yours for later.
		</p>
		<label class="label w-fit cursor-pointer gap-3 text-base-content">
			<input
				type="checkbox"
				class="toggle toggle-primary"
				bind:checked={enabled}
				disabled={busy}
				onchange={() => toggle(enabled)}
			/>
			Show my custom titles and images
			{#if busy}<span class="loading loading-xs loading-spinner"></span>{/if}
		</label>
	</div>
</section>

<script lang="ts">
	import AdminBackups from '$lib/components/AdminBackups.svelte';
	import AdminCorrections from '$lib/components/AdminCorrections.svelte';
	import AdminDiscoverCache from '$lib/components/AdminDiscoverCache.svelte';
	import CustomDisplaySettings from '$lib/components/CustomDisplaySettings.svelte';
	import LandingPage from '$lib/components/LandingPage.svelte';
	import MyCorrections from '$lib/components/MyCorrections.svelte';
	import WatchlistTransfer from '$lib/components/WatchlistTransfer.svelte';
	import { user, userLoaded } from '$lib/stores/user';
</script>

<svelte:head><title>Settings · BeanTrack</title></svelte:head>

{#if !$userLoaded}
	<div class="flex justify-center py-24"><span class="loading loading-lg loading-spinner"></span></div>
{:else if !$user}
	<LandingPage />
{:else}
	<h1 class="mb-4 text-2xl font-bold">Settings</h1>
	<div class="flex max-w-3xl flex-col gap-6">
		<CustomDisplaySettings />
		<MyCorrections />
		<WatchlistTransfer />
		{#if $user.role === 'admin'}
			<AdminCorrections />
			<AdminBackups />
			<AdminDiscoverCache />
		{/if}
	</div>
{/if}

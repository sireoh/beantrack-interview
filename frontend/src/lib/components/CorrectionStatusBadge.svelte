<script lang="ts">
	import type { CorrectionStatus } from '$lib/api/types';

	let { status }: { status: CorrectionStatus } = $props();

	const STYLES: Record<CorrectionStatus, { cls: string; label: string }> = {
		pending: { cls: 'badge-warning', label: 'Pending' },
		approved: { cls: 'badge-success', label: 'Approved' },
		rejected: { cls: 'badge-error', label: 'Rejected' }
	};
</script>

<span class="badge badge-sm {STYLES[status].cls}">{STYLES[status].label}</span>

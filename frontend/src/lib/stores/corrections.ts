/**
 * The user's own catalogue corrections (GET /api/corrections/mine). Fetched once, then patched
 * with the server's copy after each submit, like the list stores. Used by "My submissions" in
 * settings and by the edit panel to tell whether a show already has a pending correction.
 */
import { get, writable } from 'svelte/store';
import { api } from '$lib/api/client';
import type { ShowCorrection } from '$lib/api/types';

/** Newest first, as the API returns them; null until loaded. */
export const myCorrections = writable<ShowCorrection[] | null>(null);

let loading: Promise<ShowCorrection[]> | null = null;

/** Fetch my corrections unless already loaded (concurrent callers share one request). */
export function ensureMyCorrections(): Promise<ShowCorrection[]> {
	const current = get(myCorrections);
	if (current) return Promise.resolve(current);
	loading ??= api
		.myCorrections()
		.then((list) => {
			myCorrections.set(list);
			return list;
		})
		.finally(() => {
			loading = null;
		});
	return loading;
}

/** Refetch, e.g. after an admin reviewed one of their own corrections. */
export function refreshMyCorrections(): Promise<ShowCorrection[]> {
	myCorrections.set(null);
	return ensureMyCorrections();
}

/**
 * Put the server's copy of a submitted correction in the store. A resubmit while pending keeps
 * the same id (second-correction rule), so it replaces that row and moves it to the top.
 */
export function upsertMyCorrection(correction: ShowCorrection): void {
	myCorrections.update((list) =>
		list ? [correction, ...list.filter((c) => c.id !== correction.id)] : list
	);
}

/** The user's pending correction for a show, if any. */
export function pendingCorrectionFor(
	list: ShowCorrection[] | null,
	imdb: string
): ShowCorrection | undefined {
	return list?.find((c) => c.imdb_id === imdb && c.status === 'pending');
}

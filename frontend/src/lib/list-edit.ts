/**
 * Edit actions shared by the desktop edit dropdown and the mobile edit modal:
 * episode loading, +/- progress, jump to an episode, status changes, episode search, and the
 * title/image override and correction.
 * Every action updates the list stores with the server's response.
 */
import { api } from '$lib/api/client';
import type { Episode, MovieListEntry, ShowCorrection, TvListEntry } from '$lib/api/types';
import type { WatchStatus } from '$lib/status';
import { upsertMyCorrection } from '$lib/stores/corrections';
import { ensureEpisodes } from '$lib/stores/episodes';
import {
	removeMovieEntry,
	removeTvEntry,
	replaceMovieEntry,
	replaceTvEntry
} from '$lib/stores/lists';

export { ensureEpisodes as loadEpisodes };

export const clampIndex = (index: number, episodeCount: number): number =>
	Math.min(Math.max(index, 0), Math.max(episodeCount - 1, 0));

/** The episode the index points at, after clamping into range. */
export function episodeAt(episodes: Episode[], index: number): Episode | undefined {
	return episodes[clampIndex(index, episodes.length)];
}

/** Whether +/- would actually change anything (always true until progress is first saved). */
export function canStep(entry: TvListEntry, episodes: Episode[], delta: 1 | -1): boolean {
	if (episodes.length === 0) return false;
	if (entry.current_episode_metadata === null) return true;
	return clampIndex(entry.current_episode + delta, episodes.length) !== entry.current_episode;
}

/** Move progress by one episode (`delta`), sending the episode at the new index. */
export async function stepProgress(entry: TvListEntry, delta: 1 | -1): Promise<void> {
	const list = await ensureEpisodes(entry.show.imdb);
	const next = episodeAt(list, entry.current_episode + delta);
	if (!next) return;
	const updated = await api.updateTvProgress(entry.show.imdb, {
		delta,
		current_episode_metadata: next
	});
	replaceTvEntry(updated);
}

/** Jump straight to the episode at `index` (`set_to`). */
export async function jumpToEpisode(entry: TvListEntry, index: number): Promise<void> {
	const list = await ensureEpisodes(entry.show.imdb);
	const target = list[index];
	if (!target) return;
	const updated = await api.updateTvProgress(entry.show.imdb, {
		set_to: index,
		current_episode_metadata: target
	});
	replaceTvEntry(updated);
}

export async function setTvStatus(entry: TvListEntry, status: WatchStatus): Promise<void> {
	if (status === entry.status) return;
	replaceTvEntry(await api.updateTvStatus(entry.show.imdb, status));
}

export async function setMovieStatus(entry: MovieListEntry, status: WatchStatus): Promise<void> {
	if (status === entry.status) return;
	replaceMovieEntry(await api.updateMovieStatus(entry.movie.imdb, status));
}

export async function deleteTvEntry(imdb: string): Promise<void> {
	await api.deleteTv(imdb);
	removeTvEntry(imdb);
}

export async function deleteMovieEntry(imdb: string): Promise<void> {
	await api.deleteMovie(imdb);
	removeMovieEntry(imdb);
}

/** `S1.E2`, or `S1 Special` for episodes without a number. */
export function episodeCode(episode: Pick<Episode, 'season' | 'number'>): string {
	return episode.number === null
		? `S${episode.season} Special`
		: `S${episode.season}.E${episode.number}`;
}

export interface IndexedEpisode {
	episode: Episode;
	/** Position in the full episode list: the value for `set_to`. */
	index: number;
}

/**
 * Filter episodes by title, or by `season.episode` notation:
 * `2.5` -> S2E5, `2.` -> all of season 2, `s2e5` also works.
 */
export function filterEpisodes(episodes: Episode[], query: string): IndexedEpisode[] {
	const all = episodes.map((episode, index) => ({ episode, index }));
	const q = query.trim().toLowerCase();
	if (!q) return all;

	const code = q.match(/^s?(\d+)\s*(?:[.x]|e)\s*(\d*)$/);
	if (code) {
		const season = Number(code[1]);
		const number = code[2] ? Number(code[2]) : null;
		return all.filter(
			({ episode }) =>
				episode.season === season && (number === null || episode.number === number)
		);
	}
	return all.filter(({ episode }) => episode.title.toLowerCase().includes(q));
}

// --- Title & image: personal overrides and catalogue corrections -----------------

export const TITLE_MAX_LENGTH = 255; // backend app/models/corrections.py
export const IMAGE_MAX_LENGTH = 512;

/** Trimmed title/image from the edit form; empty fields are left out. */
export interface TitleImageFields {
	title?: string;
	image?: string;
}

/**
 * Validate the title/image form the way the backend does (at least one field, not blank,
 * image a plain http(s) URL). Returns the fields to send, or an error message.
 */
export function readTitleImage(
	title: string,
	image: string
): { fields: TitleImageFields } | { error: string } {
	const t = title.trim();
	const i = image.trim();
	if (!t && !i) return { error: 'Enter a title, an image URL, or both.' };
	if (t.length > TITLE_MAX_LENGTH) return { error: `Titles are at most ${TITLE_MAX_LENGTH} characters.` };
	if (i && !/^https?:\/\/\S+$/.test(i)) return { error: 'The image must be an http(s) URL.' };
	if (i.length > IMAGE_MAX_LENGTH) return { error: `Image URLs are at most ${IMAGE_MAX_LENGTH} characters.` };
	const fields: TitleImageFields = {};
	if (t) fields.title = t;
	if (i) fields.image = i;
	return { fields };
}

/** Set this user's own title/image for a show. Applies at once, only for them. */
export async function setTvOverride(entry: TvListEntry, fields: TitleImageFields): Promise<void> {
	const updated = await api.setTvOverride(entry.show.imdb, {
		custom_title: fields.title,
		custom_image: fields.image
	});
	replaceTvEntry(updated);
}

/**
 * Remove the user's override. DELETE returns 204, so the row falls back to the shared values,
 * which every entry carries as `show.catalog_*`.
 */
export async function removeTvOverride(entry: TvListEntry): Promise<void> {
	await api.deleteTvOverride(entry.show.imdb);
	replaceTvEntry({
		...entry,
		show: { ...entry.show, title: entry.show.catalog_title, image: entry.show.catalog_image },
		override: null,
		override_active: false
	});
}

/**
 * Propose a title/image fix for everyone. Nothing on screen changes until an admin approves
 * it, so only the "my corrections" store is updated, never the list entry.
 */
export async function submitCorrection(
	entry: TvListEntry,
	fields: TitleImageFields
): Promise<ShowCorrection> {
	const correction = await api.submitCorrection({
		imdb_id: entry.show.imdb,
		new_title: fields.title,
		new_image: fields.image
	});
	upsertMyCorrection(correction);
	return correction;
}

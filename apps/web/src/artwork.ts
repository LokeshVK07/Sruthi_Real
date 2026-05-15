import type { Album, Song } from "./types";

export const fallbackArt =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 800'><defs><linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='%23191343'/><stop offset='45%' stop-color='%235320bf'/><stop offset='100%' stop-color='%23e668ff'/></linearGradient></defs><rect width='800' height='800' rx='44' fill='url(%23g)'/><path d='M518 168v296c0 30-24 55-69 71-34 12-78 11-98-4-21-14-18-39 6-54 22-14 55-20 84-16V245l166-36v211c0 31-24 56-69 72-35 12-78 11-99-4-21-15-17-39 7-54 21-14 54-20 84-16V168h-12Z' fill='white' fill-opacity='.9'/></svg>";

type SongArtworkLike = Pick<Song, "artworkUrl" | "albumArtUrl" | "imageUrl" | "coverUrl">;
type AlbumArtworkLike = Pick<Album, "imageUrl" | "coverUrl">;

export function imageForSong(song?: SongArtworkLike | null) {
  return song?.artworkUrl || song?.albumArtUrl || song?.imageUrl || song?.coverUrl || fallbackArt;
}

export function imageForAlbum(album?: AlbumArtworkLike | null) {
  return album?.imageUrl || album?.coverUrl || fallbackArt;
}

export function replaceBrokenArtwork(event: { currentTarget: HTMLImageElement }) {
  if (event.currentTarget.src !== fallbackArt) {
    event.currentTarget.src = fallbackArt;
  }
}

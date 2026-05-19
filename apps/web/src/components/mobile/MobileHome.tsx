import { Bell, ChevronRight, Heart, MoreHorizontal, Play, Plus } from "lucide-react";
import type { RefreshStatus, Song } from "../../types";
import AbstractCover from "../AbstractCover";

type PlaylistSummary = { id: string; name: string; count: number };

type MobileHomeProps = {
  appName: string;
  favorites: Song[];
  recentlyPlayed: Song[];
  refreshStatus?: RefreshStatus | null;
  searchQuery: string;
  favoriteCount: number;
  playlists: PlaylistSummary[];
  onQueryChange: (value: string) => void;
  onOpenSearch: () => void;
  onOpenRefresh: () => void;
  onOpenSettings: () => void;
  onPlayTrack: (track: Song, sourceQueue?: Song[]) => void;
  onViewPlaylists: () => void;
  onViewRecent: () => void;
  onOpenPlaylist: (playlistId: string) => void;
  onOpenFavorites: () => void;
  onCreatePlaylist: () => void;
  onPrefetchTrack?: (track: Song) => void;
};

function formatDuration(seconds?: number | null) {
  if (!Number.isFinite(seconds) || !seconds || seconds <= 0) return "";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export default function MobileHome({
  appName,
  favorites,
  recentlyPlayed,
  favoriteCount,
  playlists,
  onOpenRefresh,
  onPlayTrack,
  onViewPlaylists,
  onViewRecent,
  onOpenPlaylist,
  onOpenFavorites,
  onCreatePlaylist,
  onPrefetchTrack,
}: MobileHomeProps) {
  const favoritePreview = favorites.slice(0, 8);
  const playlistPreview = playlists.filter((playlist) => playlist.id !== "favorites").slice(0, 8);

  return (
    <div className="mobile-screen mobile-home">
      <header className="mobile-screen__header mobile-screen__header--branded">
        <div className="mobile-brand">
          <span className="mobile-brand__logo">V</span>
          <div className="mobile-brand__copy">
            <strong>{appName}</strong>
            <span>Light, calm, Tamil music</span>
          </div>
        </div>
        <button type="button" className="mobile-icon-button" onClick={onOpenRefresh} aria-label="Notifications and refresh status">
          <Bell size={19} />
        </button>
      </header>

      <section className="mobile-section">
        <div className="mobile-section__header">
          <h2>Favorites</h2>
          <button type="button" onClick={onOpenFavorites}>
            View all
            <ChevronRight size={15} />
          </button>
        </div>
        <div className="mobile-card-row">
          {favoritePreview.length ? (
            favoritePreview.map((track) => (
              <button
                key={track.id}
                type="button"
                className="mobile-track-card"
                onClick={() => onPlayTrack(track, favorites)}
                onMouseEnter={() => onPrefetchTrack?.(track)}
              >
                <AbstractCover seed={track.id || track.title} size="lg" className="mobile-track-card__art" />
                <span className="mobile-track-card__play">
                  <Play size={15} fill="currentColor" />
                </span>
                <strong title={track.title}>{track.title}</strong>
                <em title={track.artist}>{track.artist || formatDuration(track.durationSeconds)}</em>
              </button>
            ))
          ) : (
            <button type="button" className="mobile-track-card mobile-track-card--empty" onClick={onOpenFavorites}>
              <AbstractCover seed="empty-favorites" size="lg" variant="leaf" className="mobile-track-card__art" />
              <strong>No favorites yet</strong>
              <em>Tap hearts to save songs</em>
            </button>
          )}
        </div>
      </section>

      <section className="mobile-section">
        <div className="mobile-section__header">
          <h2>Playlists</h2>
          <button type="button" onClick={onViewPlaylists}>
            View all
            <ChevronRight size={15} />
          </button>
        </div>
        <div className="mobile-playlists-row">
          <button type="button" className="mobile-playlist-card mobile-playlist-card--favorites" onClick={onOpenFavorites}>
            <AbstractCover seed="favorites-card" size="md" variant="rings" className="mobile-playlist-card__art" />
            <strong title="Favorites">Favorites</strong>
            <span>{favoriteCount} {favoriteCount === 1 ? "song" : "songs"}</span>
          </button>

          {playlistPreview.map((playlist) => (
            <button key={playlist.id} type="button" className="mobile-playlist-card" onClick={() => onOpenPlaylist(playlist.id)}>
              <AbstractCover seed={playlist.id || playlist.name} size="md" variant="hills" className="mobile-playlist-card__art" />
              <strong title={playlist.name}>{playlist.name}</strong>
              <span>{playlist.count} {playlist.count === 1 ? "song" : "songs"}</span>
            </button>
          ))}

          <button type="button" className="mobile-playlist-card mobile-playlist-card--new" onClick={onCreatePlaylist}>
            <span className="mobile-playlist-card__art mobile-playlist-card__art--ghost">
              <Plus size={24} />
            </span>
            <strong>New playlist</strong>
            <span>Create your own</span>
          </button>
        </div>
      </section>

      <section className="mobile-section">
        <div className="mobile-section__header">
          <h2>Recently Played</h2>
          <button type="button" onClick={onViewRecent}>
            View all
            <ChevronRight size={15} />
          </button>
        </div>
        <div className="mobile-recent-list">
          {recentlyPlayed.length ? (
            recentlyPlayed.slice(0, 12).map((track) => (
              <button
                key={track.id}
                type="button"
                className="mobile-song-row"
                onClick={() => onPlayTrack(track, recentlyPlayed)}
                onMouseEnter={() => onPrefetchTrack?.(track)}
              >
                <AbstractCover seed={track.id || track.title} size="sm" className="mobile-artwork" />
                <span className="mobile-song-row__copy">
                  <strong title={track.title}>{track.title}</strong>
                  <em title={track.artist}>{track.artist}</em>
                </span>
                <span className="mobile-song-row__meta">{formatDuration(track.durationSeconds)}</span>
                <span className="mobile-song-row__action" aria-hidden="true">
                  <MoreHorizontal size={17} />
                </span>
              </button>
            ))
          ) : (
            <div className="mobile-empty-state">No songs played yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}

import { Heart, ListMusic, Plus, Users } from "lucide-react";
import type { Song } from "../../types";
import AbstractCover from "../AbstractCover";
import type { MobileLibrarySection } from "./MobileLayout";
import { imageForSong } from "../../utils/artwork";

type PlaylistSummary = { id: string; name: string; count: number };

type MobileLibraryProps = {
  activeSection: MobileLibrarySection;
  favorites: Song[];
  recentlyPlayed: Song[];
  playlists: PlaylistSummary[];
  artists: Array<{ artist: string; songCount: number }>;
  onSectionChange: (section: MobileLibrarySection) => void;
  onCreatePlaylist: () => void;
  onOpenPlaylist: (playlistId: string) => void;
  onOpenArtist: (artist: string) => void;
  onPlayTrack: (song: Song, sourceQueue?: Song[]) => void;
};

const tabs: Array<{ key: MobileLibrarySection; label: string }> = [
  { key: "playlists", label: "Playlists" },
  { key: "favorites", label: "Favorites" },
  { key: "downloaded", label: "Downloaded" },
  { key: "recent", label: "Recently Played" },
];

function formatDuration(seconds?: number | null) {
  if (!Number.isFinite(seconds) || !seconds || seconds <= 0) return "";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function SongList({ songs, empty, onPlay }: { songs: Song[]; empty: string; onPlay: (song: Song) => void }) {
  if (!songs.length) return <div className="mobile-empty-state">{empty}</div>;
  return (
    <div className="mobile-recent-list">
      {songs.map((song) => (
        <button key={song.id} type="button" className="mobile-song-row" onClick={() => onPlay(song)}>
          <AbstractCover src={imageForSong(song)} alt={song.title} seed={song.id || song.title} size="sm" className="mobile-artwork" />
          <span className="mobile-song-row__copy">
            <strong>{song.title}</strong>
            <em>{song.artist}</em>
          </span>
          <span className="mobile-song-row__meta">{formatDuration(song.durationSeconds)}</span>
        </button>
      ))}
    </div>
  );
}

export default function MobileLibrary({
  activeSection,
  favorites,
  recentlyPlayed,
  playlists,
  artists,
  onSectionChange,
  onCreatePlaylist,
  onOpenPlaylist,
  onOpenArtist,
  onPlayTrack,
}: MobileLibraryProps) {
  const visibleSection = tabs.some((tab) => tab.key === activeSection) ? activeSection : activeSection;

  return (
    <div className="mobile-screen mobile-library-screen">
      <div className="mobile-screen__header">
        <div>
          <strong>Library</strong>
          <span>Your music, lists, and history</span>
        </div>
        <button type="button" className="mobile-icon-button" onClick={onCreatePlaylist} aria-label="Create playlist">
          <Plus size={19} />
        </button>
      </div>

      <div className="mobile-chip-row" role="tablist" aria-label="Library sections">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={visibleSection === tab.key ? "mobile-chip is-active" : "mobile-chip"}
            onClick={() => onSectionChange(tab.key)}
            role="tab"
            aria-selected={visibleSection === tab.key}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {visibleSection === "playlists" ? (
        <div className="mobile-library-grid">
          <button type="button" className="mobile-library-tile" onClick={() => onSectionChange("favorites")}>
            <AbstractCover seed="favorites-playlist" size="md" variant="rings" className="mobile-library-tile__art" />
            <span>
              <strong>Favorites</strong>
              <em>{favorites.length} songs</em>
            </span>
          </button>
          {playlists.filter((playlist) => playlist.id !== "favorites").map((playlist) => (
            <button key={playlist.id} type="button" className="mobile-library-tile" onClick={() => onOpenPlaylist(playlist.id)}>
              <AbstractCover seed={playlist.id || playlist.name} size="md" variant="wave" className="mobile-library-tile__art" />
              <span>
                <strong>{playlist.name}</strong>
                <em>{playlist.count} songs</em>
              </span>
            </button>
          ))}
          <button type="button" className="mobile-library-tile mobile-library-tile--new" onClick={onCreatePlaylist}>
            <span className="mobile-library-tile__new">
              <Plus size={22} />
            </span>
            <span>
              <strong>New Playlist</strong>
              <em>Create a calm mix</em>
            </span>
          </button>
        </div>
      ) : null}

      {visibleSection === "favorites" ? (
        <SongList songs={favorites} empty="No favorites yet. Tap the heart on songs you love." onPlay={(song) => onPlayTrack(song, favorites)} />
      ) : null}

      {visibleSection === "downloaded" ? (
        <div className="mobile-empty-state mobile-empty-state--tall">
          Downloaded songs are not available on this device yet.
        </div>
      ) : null}

      {visibleSection === "recent" ? (
        <SongList songs={recentlyPlayed} empty="Recently played songs will appear here." onPlay={(song) => onPlayTrack(song, recentlyPlayed)} />
      ) : null}

      {visibleSection === "artists" ? (
        <div className="mobile-more-list">
          {artists.slice(0, 60).map((artist) => (
            <button key={artist.artist} type="button" className="mobile-more-row" onClick={() => onOpenArtist(artist.artist)}>
              <span className="mobile-more-row__icon">
                <Users size={18} />
              </span>
              <span className="mobile-more-row__copy">
                <strong>{artist.artist}</strong>
                <em>{artist.songCount} songs</em>
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {visibleSection === "albums" ? (
        <div className="mobile-empty-state mobile-empty-state--tall">
          Albums are available from Search for now.
        </div>
      ) : null}

      <div className="mobile-library-shortcuts" aria-hidden="true">
        <span><Heart size={14} /> {favorites.length}</span>
        <span><ListMusic size={14} /> {playlists.length}</span>
      </div>
    </div>
  );
}

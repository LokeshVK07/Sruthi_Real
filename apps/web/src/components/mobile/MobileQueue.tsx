import { GripVertical, Pause, Play, SkipBack, SkipForward, Trash2 } from "lucide-react";
import type { Song } from "../../types";
import AbstractCover from "../AbstractCover";
import { imageForSong } from "../../utils/artwork";

type MobileQueueProps = {
  queue: Song[];
  currentSong: Song | null;
  currentSongId?: string;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  onPlay: (song: Song) => void;
  onClear: () => void;
  onMove: (from: number, to: number) => void;
  onRemove: (songId: string) => void;
  onPrevious: () => void;
  onNext: () => void;
  onTogglePlay: () => void;
};

function formatDuration(seconds?: number | null) {
  if (!Number.isFinite(seconds) || !seconds || seconds <= 0) return "";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function totalDurationLabel(queue: Song[]) {
  const total = queue.reduce((sum, song) => sum + (Number.isFinite(song.durationSeconds) ? song.durationSeconds || 0 : 0), 0);
  if (!total) return `${queue.length} songs`;
  const mins = Math.round(total / 60);
  return `${queue.length} songs, ${mins} min`;
}

export default function MobileQueue({
  queue,
  currentSong,
  currentSongId,
  currentTime,
  duration,
  isPlaying,
  onPlay,
  onClear,
  onMove,
  onRemove,
  onPrevious,
  onNext,
  onTogglePlay,
}: MobileQueueProps) {
  const progress = duration > 0 && Number.isFinite(duration) ? Math.min(100, Math.max(0, (currentTime / duration) * 100)) : 0;
  const upNext = queue.length ? queue : currentSong ? [currentSong] : [];

  return (
    <div className="mobile-screen mobile-queue-screen">
      <div className="mobile-screen__header mobile-screen__header--loose">
        <div>
          <strong>Queue</strong>
          <span>{totalDurationLabel(upNext)}</span>
        </div>
        <button type="button" className="mobile-text-button" onClick={onClear} disabled={!queue.length}>
          Clear
        </button>
      </div>

      {currentSong ? (
        <section className="mobile-queue-now" aria-label="Now playing">
          <AbstractCover src={imageForSong(currentSong)} alt={currentSong.title} seed={currentSong.id || currentSong.title} size="md" className="mobile-queue-now__art" active />
          <div className="mobile-queue-now__copy">
            <span>Now Playing</span>
            <strong>{currentSong.title}</strong>
            <em>{currentSong.artist}</em>
            <div className="mobile-queue-now__progress">
              <span style={{ width: `${progress}%` }} />
            </div>
          </div>
          <div className="mobile-queue-now__controls">
            <button type="button" onClick={onPrevious} aria-label="Previous track">
              <SkipBack size={18} />
            </button>
            <button type="button" className="mobile-queue-now__play" onClick={onTogglePlay} aria-label="Play or pause">
              {isPlaying ? <Pause size={18} /> : <Play size={18} />}
            </button>
            <button type="button" onClick={onNext} aria-label="Next track">
              <SkipForward size={18} />
            </button>
          </div>
        </section>
      ) : (
        <div className="mobile-empty-state">Pick a song to build your queue.</div>
      )}

      <section className="mobile-section">
        <div className="mobile-section__header">
          <h2>Up Next</h2>
        </div>
        <div className="mobile-queue-list">
          {upNext.length ? (
            upNext.map((song, index) => {
              const active = song.id === currentSongId;
              return (
                <div key={`${song.id}-${index}`} className={active ? "mobile-queue-row is-active" : "mobile-queue-row"}>
                  <button type="button" className="mobile-queue-row__main" onClick={() => onPlay(song)} aria-label={`Play ${song.title}`}>
                    <AbstractCover src={imageForSong(song)} alt={song.title} seed={song.id || song.title} size="sm" className="mobile-artwork" active={active} />
                    <span className="mobile-queue-row__copy">
                      <strong>{song.title}</strong>
                      <em>{song.artist}</em>
                    </span>
                  </button>
                  <span className="mobile-queue-row__duration">{formatDuration(song.durationSeconds)}</span>
                  <div className="mobile-queue-row__actions">
                    <button type="button" onClick={() => onMove(index, Math.max(0, index - 1))} aria-label="Move earlier" disabled={index === 0}>
                      <GripVertical size={17} />
                    </button>
                    <button type="button" onClick={() => onRemove(song.id)} aria-label="Remove from queue">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="mobile-empty-state">Your queue is empty.</div>
          )}
        </div>
      </section>
    </div>
  );
}

import { useRef } from "react";
import { ChevronUp, Pause, Play, SkipBack, SkipForward } from "lucide-react";
import type { Song } from "../../types";
import AbstractCover from "../AbstractCover";
import { imageForSong } from "../../utils/artwork";

type MobileMiniPlayerProps = {
  song: Song;
  artwork: string;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onOpenPlayer: () => void;
};

export default function MobileMiniPlayer({
  song,
  artwork,
  currentTime,
  duration,
  isPlaying,
  onTogglePlay,
  onPrevious,
  onNext,
  onOpenPlayer,
}: MobileMiniPlayerProps) {
  const touchStartY = useRef<number | null>(null);
  const progress = duration > 0 ? Math.min(100, Math.max(0, (currentTime / duration) * 100)) : 0;

  return (
    <div
      className="mobile-mini-player"
      onTouchStart={(event) => {
        touchStartY.current = event.touches[0]?.clientY ?? null;
      }}
      onTouchEnd={(event) => {
        const startY = touchStartY.current;
        touchStartY.current = null;
        const endY = event.changedTouches[0]?.clientY;
        if (startY != null && endY != null && startY - endY > 42) {
          onOpenPlayer();
        }
      }}
    >
      <button type="button" className="mobile-mini-player__main" onClick={onOpenPlayer}>
        <AbstractCover src={artwork || imageForSong(song)} alt={song.title} seed={song.id || song.title} size="sm" className="mobile-artwork" />
        <div className="mobile-mini-player__copy">
          <strong title={song.title}>{song.title}</strong>
          <span title={song.artist}>{song.artist}</span>
          <div className="mobile-mini-player__bar">
            <span style={{ width: `${progress}%` }} />
          </div>
        </div>
      </button>
      <div className="mobile-mini-player__actions">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onPrevious();
          }}
          aria-label="Previous track"
        >
          <SkipBack size={18} />
        </button>
        <button
          type="button"
          className="mobile-mini-player__play"
          onClick={(event) => {
            event.stopPropagation();
            onTogglePlay();
          }}
          aria-label="Toggle playback"
        >
          {isPlaying ? <Pause size={20} /> : <Play size={20} />}
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onNext();
          }}
          aria-label="Next track"
        >
          <SkipForward size={18} />
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onOpenPlayer();
          }}
          aria-label="Expand player"
        >
          <ChevronUp size={18} />
        </button>
      </div>
    </div>
  );
}

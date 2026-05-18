import { Trash2, X, ChevronUp, ChevronDown, GripVertical } from "lucide-react";
import type { Song } from "../../types";
import AbstractCover from "../AbstractCover";
import { imageForSong } from "../../utils/artwork";

type MobileQueueSheetProps = {
  open: boolean;
  queue: Song[];
  currentSongId?: string;
  fallbackArt: string;
  onClose: () => void;
  onPlay: (song: Song) => void;
  onClear: () => void;
  onRemove: (songId: string) => void;
  onMove: (from: number, to: number) => void;
};

export default function MobileQueueSheet({
  open,
  queue,
  currentSongId,
  fallbackArt: _fallbackArt,
  onClose,
  onPlay,
  onClear,
  onRemove,
  onMove,
}: MobileQueueSheetProps) {
  if (!open) return null;

  return (
    <div className="mobile-sheet-backdrop" onClick={onClose}>
      <div className="mobile-bottom-sheet mobile-queue-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-sheet-handle" />
        <div className="mobile-sheet-header">
          <div>
            <span className="mobile-pill">UP NEXT</span>
            <h2>Queue</h2>
            <small>{queue.length} songs</small>
          </div>
          <button type="button" onClick={onClear}>Clear</button>
        </div>
        <div className="mobile-queue-sheet__list">
          {queue.map((song, index) => (
            <div key={`${song.id}-${index}`} className={song.id === currentSongId ? "mobile-queue-row is-active" : "mobile-queue-row"}>
              <button type="button" className="mobile-queue-row__main" onClick={() => onPlay(song)}>
                <AbstractCover src={imageForSong(song)} alt={song.title} seed={song.id || song.title} size="sm" className="mobile-artwork" />
                <div className="mobile-queue-row__copy">
                  <strong title={song.title}>{song.title}</strong>
                  <span title={song.artist}>{song.artist}</span>
                </div>
              </button>
              <div className="mobile-queue-row__actions">
                <button type="button" onClick={() => onMove(index, Math.max(0, index - 1))} aria-label="Move up">
                  <ChevronUp size={14} />
                </button>
                <button type="button" onClick={() => onMove(index, Math.min(queue.length - 1, index + 1))} aria-label="Move down">
                  <ChevronDown size={14} />
                </button>
                <button type="button" aria-label="Queue order">
                  <GripVertical size={14} />
                </button>
                <button type="button" onClick={() => onRemove(song.id)} aria-label="Remove from queue">
                  <X size={14} />
                </button>
              </div>
            </div>
          ))}
          {!queue.length ? <div className="mobile-empty-state">Your queue is empty.</div> : null}
        </div>
      </div>
    </div>
  );
}

import { GripVertical, Play } from "lucide-react";
import { useState } from "react";
import type { Song } from "../types";
import AbstractCover from "./AbstractCover";
import { imageForSong } from "../utils/artwork";

type QueuePanelProps = {
  queue: Song[];
  fallbackArt: string;
  currentSongId?: string;
  onPlay: (song: Song) => void;
  onReorder: (from: number, to: number) => void;
  onClear: () => void;
};

export default function QueuePanel({ queue, fallbackArt: _fallbackArt, currentSongId, onPlay, onReorder, onClear }: QueuePanelProps) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  function resetDragState() {
    setDragIndex(null);
    setDragOverIndex(null);
  }

  function handleDrop(targetIndex: number) {
    if (dragIndex === null || dragIndex === targetIndex) {
      resetDragState();
      return;
    }
    onReorder(dragIndex, targetIndex);
    resetDragState();
  }

  return (
    <aside className="queue-panel">
      <div className="queue-panel__header">
        <div>
          <h2>Queue</h2>
        </div>
        <button className="queue-panel__clear" onClick={onClear}>
          Clear
        </button>
      </div>

      <div className="queue-panel__list">
        {queue.length ? (
          queue.map((song, index) => (
            <div
              key={`${song.id}-${index}`}
              className={[
                "queue-item",
                song.id === currentSongId ? "is-active" : "",
                dragIndex === index ? "is-dragging" : "",
                dragOverIndex === index ? "is-drop-target" : ""
              ]
                .filter(Boolean)
                .join(" ")}
              onDragOver={(event) => {
                event.preventDefault();
                if (dragOverIndex !== index) {
                  setDragOverIndex(index);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                handleDrop(index);
              }}
            >
              <button className="queue-item__main" onClick={() => onPlay(song)}>
                <span className="queue-item__playing" aria-hidden="true">
                  {song.id === currentSongId ? (
                    <Play size={10} fill="currentColor" />
                  ) : null}
                </span>
                <AbstractCover src={imageForSong(song)} alt={song.title} seed={song.id || song.title} size="xs" active={song.id === currentSongId} />
                <div className="queue-item__copy">
                  <strong title={song.title}>{song.title}</strong>
                  <span title={song.artist}>{song.artist}</span>
                </div>
              </button>
              <button
                type="button"
                className="queue-item__handle"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = "move";
                  event.dataTransfer.setData("text/plain", song.id);
                  setDragIndex(index);
                  setDragOverIndex(index);
                }}
                onDragEnd={resetDragState}
                aria-label="Drag to reorder queue"
                title="Drag to reorder queue"
              >
                <GripVertical size={16} />
              </button>
            </div>
          ))
        ) : (
          <div className="queue-panel__empty">
            <p>Your queue is empty. Pick a track from the center dashboard to start building it.</p>
          </div>
        )}
      </div>
    </aside>
  );
}

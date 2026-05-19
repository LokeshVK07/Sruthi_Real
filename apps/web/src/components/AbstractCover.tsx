type AbstractCoverVariant = "wave" | "bars" | "rings" | "dots" | "lines" | "leaf" | "hills";
type AbstractCoverSize = "xs" | "sm" | "md" | "lg" | "hero";

type AbstractCoverProps = {
  src?: string | null;
  alt?: string;
  variant?: AbstractCoverVariant;
  size?: AbstractCoverSize;
  active?: boolean;
  seed?: string | number | null;
  className?: string;
};

const variants: AbstractCoverVariant[] = ["wave", "bars", "rings", "dots", "lines", "leaf", "hills"];

function hashSeed(seed?: string | number | null) {
  const text = String(seed ?? "vibe");
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash << 5) - hash + text.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function pickCoverVariant(seed?: string | number | null) {
  return variants[hashSeed(seed) % variants.length];
}

export default function AbstractCover({ src, alt = "", variant, size = "md", active = false, seed, className = "" }: AbstractCoverProps) {
  const resolvedVariant = variant ?? pickCoverVariant(seed);
  const offset = hashSeed(seed) % 19;
  const classes = ["abstract-cover", `abstract-cover--${resolvedVariant}`, `abstract-cover--${size}`, active ? "is-active" : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes} aria-hidden="true" style={{ "--cover-shift": `${offset}px` } as CSSProperties}>
      {src ? <img className="abstract-cover__image" src={src} alt={alt} loading="lazy" decoding="async" /> : null}
      {resolvedVariant === "bars" ? (
        <span className="abstract-cover__bars">
          {Array.from({ length: 9 }).map((_, index) => (
            <span key={index} style={{ "--bar-index": index } as React.CSSProperties} />
          ))}
        </span>
      ) : null}
      {resolvedVariant === "dots" ? <span className="abstract-cover__dots" /> : null}
      {resolvedVariant === "rings" ? <span className="abstract-cover__rings" /> : null}
      {resolvedVariant === "leaf" ? (
        <span className="abstract-cover__leaf">
          <span />
          <span />
          <span />
        </span>
      ) : null}
      {resolvedVariant === "hills" ? (
        <svg className="abstract-cover__svg" viewBox="0 0 180 140" role="presentation" focusable="false">
          <path d="M0 112 C 28 78, 48 70, 78 96 C 112 126, 134 74, 180 82" />
          <path d="M0 128 C 30 94, 58 92, 90 112 C 122 132, 142 104, 180 112" />
          <path d="M18 92 C 44 58, 70 54, 100 76 C 132 100, 154 54, 180 62" />
        </svg>
      ) : null}
      {resolvedVariant === "wave" || resolvedVariant === "lines" ? (
        <svg className="abstract-cover__svg" viewBox="0 0 180 140" role="presentation" focusable="false">
          <path d="M-10 94 C 24 44, 58 48, 88 78 S 144 116, 194 58" />
          <path d="M-10 108 C 26 62, 62 58, 92 88 S 144 122, 194 76" />
          <path d="M-10 76 C 26 24, 62 32, 92 58 S 142 92, 194 34" />
          {resolvedVariant === "wave" ? (
            <>
              <line x1="42" y1="46" x2="42" y2="98" />
              <line x1="54" y1="30" x2="54" y2="110" />
              <line x1="66" y1="58" x2="66" y2="92" />
              <line x1="104" y1="42" x2="104" y2="104" />
              <line x1="116" y1="20" x2="116" y2="112" />
              <line x1="128" y1="38" x2="128" y2="98" />
            </>
          ) : null}
        </svg>
      ) : null}
    </span>
  );
}
import type { CSSProperties } from "react";

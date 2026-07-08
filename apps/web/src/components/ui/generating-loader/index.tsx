"use client";

import { cn } from "@/lib/utils";
import "./styles.css";

// Shared "something is generating" indicator. Composition:
//   perimeter — a perforated ring of gray dots rotating slowly (always),
//   center    — varies by `variant`:
//     "flames" (default) — vertical scanlines in mixed reds/ambers/
//                          yellows + flame-gradient lines, rising,
//     "stars"            — a few AI sparkles (4-point stars) in amber,
//                          yellow, and white that pop in, rotate, and
//                          vanish at staggered interior positions.
// At sm size the center is always a single continuously-rotating
// sparkle (regardless of variant) — the scanline / sparkle-field
// compositions don't read at 16px, but an empty center looks broken.
interface GeneratingLoaderProps {
  size?: "sm" | "md" | "lg";
  variant?: "flames" | "stars";
  label?: string;
  className?: string;
}

// Per-size geometry for the perforated dot ring. Counts are high enough
// that dots form a near-continuous dashed circle.
const DIM = {
  sm: { box: "h-4 w-4",   dots: 14, orbit: "7px",  dot: "1px"   },
  md: { box: "h-12 w-12", dots: 24, orbit: "22px", dot: "1.5px" },
  lg: { box: "h-24 w-24", dots: 32, orbit: "45px", dot: "2px"   },
} as const;

type ScanColor = "red" | "amber" | "yellow" | "flame";
interface Scanline {
  dur: string;
  delay: string;
  x: string;
  color: ScanColor;
  o: number;
}

// Scanlines: density + color mix tuned per size.
const SCANLINES_MD: Scanline[] = [
  { dur: "1.3s",  delay: "0s",    x: "-22px", color: "yellow", o: 0.45 },
  { dur: "1.5s",  delay: "-0.4s", x: "-18px", color: "amber",  o: 0.6  },
  { dur: "1.1s",  delay: "-0.9s", x: "-14px", color: "yellow", o: 0.55 },
  { dur: "1.4s",  delay: "-0.6s", x: "-11px", color: "flame",  o: 0.85 },
  { dur: "1.0s",  delay: "-1.3s", x: "-7px",  color: "amber",  o: 0.7  },
  { dur: "1.35s", delay: "-0.2s", x: "-3px",  color: "red",    o: 1    },
  { dur: "1.5s",  delay: "-1.0s", x: "1px",   color: "yellow", o: 0.55 },
  { dur: "1.05s", delay: "-1.5s", x: "5px",   color: "flame",  o: 0.9  },
  { dur: "1.45s", delay: "-0.8s", x: "9px",   color: "amber",  o: 0.6  },
  { dur: "1.15s", delay: "-1.2s", x: "13px",  color: "yellow", o: 0.5  },
  { dur: "1.3s",  delay: "-0.5s", x: "17px",  color: "flame",  o: 0.8  },
  { dur: "1.1s",  delay: "-1.6s", x: "20px",  color: "yellow", o: 0.45 },
  { dur: "1.5s",  delay: "-0.3s", x: "22px",  color: "amber",  o: 0.55 },
  { dur: "1.25s", delay: "-1.1s", x: "-19px", color: "yellow", o: 0.5  },
];

const SCANLINES_LG: Scanline[] = [
  { dur: "1.2s",  delay: "0s",    x: "-42px", color: "yellow", o: 0.4  },
  { dur: "1.4s",  delay: "-0.4s", x: "-37px", color: "amber",  o: 0.55 },
  { dur: "1.05s", delay: "-1.0s", x: "-32px", color: "yellow", o: 0.5  },
  { dur: "1.35s", delay: "-0.6s", x: "-27px", color: "flame",  o: 0.85 },
  { dur: "0.95s", delay: "-1.3s", x: "-22px", color: "amber",  o: 0.65 },
  { dur: "1.3s",  delay: "-0.2s", x: "-18px", color: "yellow", o: 0.5  },
  { dur: "1.15s", delay: "-0.9s", x: "-13px", color: "amber",  o: 0.7  },
  { dur: "1.5s",  delay: "-1.5s", x: "-9px",  color: "flame",  o: 0.85 },
  { dur: "1.0s",  delay: "-0.5s", x: "-4px",  color: "red",    o: 1    },
  { dur: "1.4s",  delay: "-1.1s", x: "0px",   color: "yellow", o: 0.55 },
  { dur: "1.25s", delay: "-1.7s", x: "4px",   color: "amber",  o: 0.65 },
  { dur: "1.0s",  delay: "-0.3s", x: "8px",   color: "flame",  o: 0.9  },
  { dur: "1.45s", delay: "-1.2s", x: "13px",  color: "amber",  o: 0.6  },
  { dur: "1.15s", delay: "-0.7s", x: "17px",  color: "yellow", o: 0.5  },
  { dur: "1.3s",  delay: "-1.4s", x: "22px",  color: "flame",  o: 0.8  },
  { dur: "1.05s", delay: "-0.6s", x: "27px",  color: "amber",  o: 0.6  },
  { dur: "1.2s",  delay: "-1.6s", x: "32px",  color: "yellow", o: 0.45 },
  { dur: "1.5s",  delay: "-0.4s", x: "37px",  color: "amber",  o: 0.55 },
  { dur: "1.1s",  delay: "-1.0s", x: "42px",  color: "yellow", o: 0.4  },
  { dur: "1.4s",  delay: "-0.8s", x: "-15px", color: "flame",  o: 0.8  },
];

const SCAN_COLOR_VAR: Record<Exclude<ScanColor, "flame">, string> = {
  red:    "var(--blaze-red)",
  amber:  "var(--blaze-amber)",
  yellow: "var(--blaze-yellow)",
};

type SparkleColor = "amber" | "yellow" | "white";
interface Sparkle {
  top: string;
  left: string;
  size: number;
  dur: string;
  delay: string;
  color: SparkleColor;
}

// Sparkles for the "stars" variant — sit inside the orb. One "hero"
// sparkle is sized to ~1/5 of the orb diameter so the composition has
// a clear focal point; the others vary smaller.
const SPARKLES_MD: Sparkle[] = [
  { top: "34%", left: "36%", size: 10, dur: "1.9s", delay: "0s",    color: "amber"  }, // hero
  { top: "30%", left: "72%", size: 5,  dur: "1.6s", delay: "-0.7s", color: "white"  },
  { top: "70%", left: "50%", size: 7,  dur: "1.7s", delay: "-1.2s", color: "yellow" },
];

const SPARKLES_LG: Sparkle[] = [
  { top: "34%", left: "36%", size: 19, dur: "2.0s", delay: "0s",    color: "amber"  }, // hero
  { top: "28%", left: "72%", size: 8,  dur: "1.6s", delay: "-0.7s", color: "white"  },
  { top: "72%", left: "30%", size: 12, dur: "1.8s", delay: "-1.3s", color: "yellow" },
  { top: "70%", left: "68%", size: 7,  dur: "1.7s", delay: "-0.4s", color: "white"  },
];

// Four-pointed AI sparkle ✦ — symmetric, reads as a single bright glint.
function SparkleSvg({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <path
        d="M12 1.5 L14 10 L22.5 12 L14 14 L12 22.5 L10 14 L1.5 12 L10 10 Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function GeneratingLoader({
  size = "md",
  variant = "flames",
  label,
  className,
}: GeneratingLoaderProps) {
  const dim = DIM[size];

  // sm always uses the center-sparkle composition (variant is ignored
  // because the field-based compositions don't read at 16px).
  const showScanlines = variant === "flames" && size !== "sm";
  const showSparkles  = variant === "stars"  && size !== "sm";
  const showCenterSparkle = size === "sm";

  const scanlines = !showScanlines
    ? []
    : size === "lg" ? SCANLINES_LG : SCANLINES_MD;
  const sparkles = !showSparkles
    ? []
    : size === "lg" ? SPARKLES_LG : SPARKLES_MD;

  // Gentle linear opacity ramp across the perforated ring — enough to make
  // rotation perceptible without making it feel like a comet.
  const dotOpacity = (i: number) => 0.25 + 0.4 * (1 - i / dim.dots);

  return (
    <div
      className={cn("inline-flex flex-col items-center gap-3 blaze-orb", className)}
      role="status"
      aria-live="polite"
      aria-label={label ?? "Generating"}
    >
      <div className={cn("relative", dim.box)}>
        {/* "flames" variant — scanlines clipped to the orb circle. */}
        {scanlines.length > 0 && (
          <div
            className="absolute inset-0 rounded-full overflow-hidden"
            aria-hidden
          >
            {scanlines.map((s, i) => (
              <span
                key={i}
                className={cn("blaze-scanline", s.color === "flame" && "flame")}
                style={{
                  // @ts-expect-error CSS custom properties
                  "--rise-dur": s.dur,
                  "--rise-delay": s.delay,
                  "--scan-x": s.x,
                  "--scan-o": s.o,
                  // Inline narrowing on s.color so TypeScript can resolve
                  // the SCAN_COLOR_VAR index without flame in the union.
                  ...(s.color === "flame"
                    ? {}
                    : { "--scan-color": SCAN_COLOR_VAR[s.color] }),
                }}
              />
            ))}
          </div>
        )}

        {/* "stars" variant — interior AI sparkles popping in/out. */}
        {sparkles.map((s, i) => (
          <span
            key={i}
            className="blaze-sparkle-pos"
            style={{
              top: s.top,
              left: s.left,
              // @ts-expect-error CSS custom properties
              "--sparkle-size": `${s.size}px`,
              "--sparkle-dur": s.dur,
              "--sparkle-delay": s.delay,
            }}
            aria-hidden
          >
            <SparkleSvg className={cn("blaze-sparkle", s.color)} />
          </span>
        ))}

        {/* sm — single continuously-rotating sparkle in the center. */}
        {showCenterSparkle && (
          <span
            className="blaze-sparkle-pos"
            style={{
              top: "50%",
              left: "50%",
              // @ts-expect-error CSS custom properties
              "--sparkle-size": "8px",
            }}
            aria-hidden
          >
            <SparkleSvg className="blaze-sparkle continuous yellow" />
          </span>
        )}

        {/* Perimeter — perforated rotating dot ring. */}
        <div
          className="absolute inset-0 blaze-sweep"
          style={{
            // @ts-expect-error CSS custom properties
            "--orbit-r": dim.orbit,
            "--dot-size": dim.dot,
          }}
          aria-hidden
        >
          {Array.from({ length: dim.dots }).map((_, i) => (
            <span
              key={i}
              className="blaze-sweep-dot"
              style={{
                // @ts-expect-error CSS custom properties
                "--i": i,
                "--n": dim.dots,
                opacity: dotOpacity(i),
              }}
            />
          ))}
        </div>
      </div>

      {label && (
        <p className={cn("blaze-label", size === "lg" ? "text-sm" : "text-xs")}>
          {label}
        </p>
      )}
    </div>
  );
}

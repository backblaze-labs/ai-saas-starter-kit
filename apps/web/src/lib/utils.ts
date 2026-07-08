import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function humanizeBytes(bytes: number) {
  for (const unit of ["B", "KB", "MB", "GB"]) {
    if (Math.abs(bytes) < 1024) {
      // No decimals for bytes, one decimal for larger units
      return unit === "B"
        ? `${Math.round(bytes)} ${unit}`
        : `${bytes.toFixed(1)} ${unit}`;
    }
    bytes /= 1024;
  }
  return `${bytes.toFixed(1)} TB`;
}

export function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

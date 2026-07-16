"use client";

import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";

interface ErrorStateProps {
  /** The thrown error — typically an ApiError. Used to derive sensible
   *  default copy when title/description aren't provided. */
  error?: unknown;
  /** Override the auto-derived title. */
  title?: string;
  /** Override the auto-derived description. */
  description?: string;
  /** Show a Retry button wired to this handler. */
  onRetry?: () => void;
  icon?: LucideIcon;
  className?: string;
}

interface DerivedCopy {
  icon: LucideIcon;
  title: string;
  description: string;
}

// Map common error shapes to calm, customer-facing copy. We deliberately do
// NOT surface operator detail here (internal URLs, dev commands, backend logs,
// B2 key permissions, or raw error text) — this primitive renders on customer
// pages. Developers still see the underlying error in the network tab; the
// customer gets a clear status and a retry.
function deriveCopy(error: unknown): DerivedCopy {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return {
        icon: WifiOff,
        title: "Can't reach the server",
        description: "Please check your connection and try again.",
      };
    }
    if (error.status === 401 || error.status === 403) {
      return {
        icon: AlertTriangle,
        title: "Not authorized",
        description:
          "You don't have access to this, or your session expired. Try signing in again.",
      };
    }
    if (error.status === 404) {
      return {
        icon: AlertTriangle,
        title: "Not found",
        description: "We couldn't find what you're looking for.",
      };
    }
  }
  return {
    icon: AlertTriangle,
    title: "Something went wrong",
    description: "Please try again in a moment.",
  };
}

/**
 * Failure-state primitive — the persistent counterpart to `EmptyState`.
 * Use whenever a fetch fails and showing stale or empty UI would mislead
 * the user into thinking the underlying state is "no data" rather than
 * "couldn't load the data."
 */
export function ErrorState({
  error,
  title,
  description,
  onRetry,
  icon,
  className,
}: ErrorStateProps) {
  const derived = deriveCopy(error);
  const Icon = icon ?? derived.icon;
  const finalTitle = title ?? derived.title;
  const finalDescription = description ?? derived.description;

  return (
    <div
      className={`flex flex-col items-center justify-center py-12 text-center ${className ?? ""}`}
      role="alert"
    >
      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-[var(--attention-subtle)] border border-[color-mix(in_oklab,var(--attention)_30%,var(--border))] mb-4">
        <Icon className="h-5 w-5 text-[var(--attention)]" />
      </div>
      <p className="text-sm font-semibold">{finalTitle}</p>
      <p className="text-sm text-muted-foreground mt-1 max-w-md">
        {finalDescription}
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-4">
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          Retry
        </Button>
      )}
    </div>
  );
}

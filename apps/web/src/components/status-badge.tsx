import { Badge } from "@/components/ui/badge";

// Shared status pill for job / subscription / provider-run statuses across the
// dashboard and the admin grids, so a status colour means the same thing
// everywhere.
const GOOD = new Set(["succeeded", "active", "trialing", "processed"]);
const BAD = new Set([
  "failed",
  "canceled",
  "cancelled",
  "past_due",
  "incomplete_expired",
]);

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const s = (status ?? "").toLowerCase();
  const variant = GOOD.has(s) ? "default" : BAD.has(s) ? "destructive" : "secondary";
  return (
    <Badge variant={variant} className="capitalize">
      {status || "unknown"}
    </Badge>
  );
}

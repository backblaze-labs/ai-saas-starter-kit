import Link from "next/link";
import { FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="flex items-center justify-center w-16 h-16 rounded-full bg-muted border border-border mb-6">
        <FileQuestion className="h-8 w-8 text-muted-foreground" />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight">
        Page not found
      </h1>
      <p className="text-sm text-muted-foreground mt-2 max-w-md">
        We couldn&apos;t find that page. It may have been moved, renamed, or
        never existed.
      </p>
      <div className="mt-6 flex gap-2">
        <Button asChild variant="outline" size="sm">
          <Link href="/">Back to dashboard</Link>
        </Button>
        <Button asChild size="sm">
          <Link href="/files">Browse files</Link>
        </Button>
      </div>
    </div>
  );
}

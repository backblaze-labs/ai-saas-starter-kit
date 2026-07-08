import Link from "next/link";
import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FileBrowser } from "@/components/files/file-browser";

export default function FilesPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Files</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Browse and manage everything in your bucket.
          </p>
        </div>
        <Button asChild size="sm" className="h-8 shrink-0">
          <Link href="/upload">
            <Upload aria-hidden="true" className="h-3.5 w-3.5" />
            Upload files
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <FileBrowser />
      </div>
    </div>
  );
}

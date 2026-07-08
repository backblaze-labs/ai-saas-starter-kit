"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Moon, Sun, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CommandPalette } from "./command-palette";
import { APP_NAME } from "@/lib/app-config";

// Overrides for routes whose label differs from the derived segment
// (e.g. "/" -> "Dashboard", "/design" -> "Design System").
const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/upload": "Upload",
  "/files": "Files",
  "/settings": "Settings",
  "/design": "Design System",
};

// Fallback page label for routes not in the override map: title-case the last
// non-empty path segment, splitting hyphens (e.g. "/file-browser" -> "File Browser").
function deriveTitleFromPath(pathname: string): string {
  const segment = pathname.split("/").filter(Boolean).pop() ?? "";
  if (!segment) return "Home";
  return segment
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function Header() {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const pageTitle = pageTitles[pathname] ?? deriveTitleFromPath(pathname);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const nextTheme = resolvedTheme === "dark" ? "light" : "dark";

  // Global keyboard shortcut — cmd/ctrl-K or `/` toggles the palette.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isTyping =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable;
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !isTyping)) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <header className="flex h-14 items-center gap-3 bg-nav text-nav-foreground px-4 border-b border-white/10">
      <SidebarTrigger className="h-8 w-8 text-nav-foreground/80 hover:text-nav-foreground hover:bg-white/10 rounded-md" />
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink
              href="/"
              className="text-nav-foreground/80 hover:text-nav-foreground font-medium"
            >
              {APP_NAME}
            </BreadcrumbLink>
          </BreadcrumbItem>
          {pathname !== "/" && (
            <>
              <BreadcrumbSeparator className="text-nav-foreground/40">
                /
              </BreadcrumbSeparator>
              <BreadcrumbItem>
                <BreadcrumbPage className="text-nav-foreground font-semibold">
                  {pageTitle}
                </BreadcrumbPage>
              </BreadcrumbItem>
            </>
          )}
        </BreadcrumbList>
      </Breadcrumb>

      <button
        type="button"
        aria-label="Open command palette"
        onClick={() => setPaletteOpen(true)}
        className="ml-4 hidden md:flex items-center gap-2 h-8 flex-1 max-w-md px-3 rounded-md bg-white/10 border border-white/15 text-nav-foreground/70 text-sm hover:bg-white/15 hover:text-nav-foreground transition-colors"
      >
        <Search className="h-3.5 w-3.5" />
        <span className="text-xs">Search files or jump to...</span>
        <kbd className="ml-auto text-[10px] font-mono border border-white/20 rounded px-1 py-0.5 text-nav-foreground/60">
          ⌘K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              aria-label="Toggle color theme"
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-nav-foreground/80 hover:text-nav-foreground hover:bg-white/10 rounded-md"
              onClick={() => setTheme(nextTheme)}
            >
              <Sun
                aria-hidden
                className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0"
              />
              <Moon
                aria-hidden
                className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100"
              />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">Toggle color theme</TooltipContent>
        </Tooltip>
        {/* Placeholder avatar — swap for a real user chip when auth lands. */}
        <div
          aria-hidden
          className="ml-1 h-7 w-7 rounded-full bg-[var(--primary)] ring-1 ring-white/20 relative overflow-hidden"
        >
          <span className="absolute inset-x-0 top-0 h-1/2 bg-white/15" />
        </div>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </header>
  );
}

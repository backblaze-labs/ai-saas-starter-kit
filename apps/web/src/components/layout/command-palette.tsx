"use client";

import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Upload,
  FolderOpen,
  Settings,
  Sparkles,
  FileIcon,
  Moon,
  Sun,
  Wand2,
  CreditCard,
  UserRound,
} from "lucide-react";
import { useTheme } from "next-themes";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { useFiles } from "@/lib/queries";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const routes = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Generate", href: "/generate", icon: Wand2 },
  { label: "Billing", href: "/billing", icon: CreditCard },
  { label: "Upload", href: "/upload", icon: Upload },
  { label: "Files", href: "/files", icon: FolderOpen },
  { label: "Account", href: "/account", icon: UserRound },
  { label: "Settings", href: "/settings", icon: Settings },
  { label: "Design System", href: "/design", icon: Sparkles },
];

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { setTheme } = useTheme();
  // Lazy-load the file index only while the palette is open, through the shared
  // TanStack Query cache (deduped with the Files page, cached, and errors handled
  // globally) rather than a bespoke useEffect + fetch that swallowed failures.
  const files = useFiles(100, open).data ?? [];

  const runThen = (fn: () => void) => () => {
    onOpenChange(false);
    fn();
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search files or jump to a page…" />
      <CommandList>
        <CommandEmpty>No matches found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {routes.map((r) => (
            <CommandItem
              key={r.href}
              onSelect={runThen(() => router.push(r.href))}
              value={`nav ${r.label}`}
            >
              <r.icon />
              {r.label}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Theme">
          <CommandItem onSelect={runThen(() => setTheme("light"))} value="theme light">
            <Sun />
            Light mode
          </CommandItem>
          <CommandItem onSelect={runThen(() => setTheme("dark"))} value="theme dark">
            <Moon />
            Dark mode
          </CommandItem>
          <CommandItem onSelect={runThen(() => setTheme("system"))} value="theme system">
            <Sparkles />
            System theme
          </CommandItem>
        </CommandGroup>
        {files.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Files">
              {files.slice(0, 20).map((f) => (
                <CommandItem
                  key={f.key}
                  value={`file ${f.filename} ${f.key}`}
                  onSelect={runThen(() => router.push("/files"))}
                >
                  <FileIcon />
                  <span className="truncate">{f.filename}</span>
                  <CommandShortcut>{f.size_human}</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}

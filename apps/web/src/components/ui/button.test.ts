import { describe, expect, it } from "vitest";

import { buttonVariants } from "./button";
import { cn } from "../../lib/utils";

// `AlertDialogAction` renders `cn(buttonVariants(), className)`. The destructive
// confirm dialogs (delete file, empty bucket) pass
// `buttonVariants({ variant: "destructive" })` as that className. This guards
// the resulting merge: the confirm button must be white-on-red (clears WCAG AA
// in both themes) and must NOT fall back to the default variant's
// `text-primary-foreground`/`bg-primary`, which previously left the label as
// inherited ink on red (failing contrast on an irreversible action).
describe("destructive confirm button (AlertDialogAction merge)", () => {
  const merged = cn(buttonVariants(), buttonVariants({ variant: "destructive" }));

  it("renders white text on the destructive surface", () => {
    expect(merged).toContain("text-white");
    expect(merged).toContain("bg-destructive");
  });

  it("darkens the destructive background in dark mode for contrast", () => {
    expect(merged).toContain("dark:bg-destructive/60");
  });

  it("does not leak the default variant's foreground/background", () => {
    expect(merged).not.toContain("text-primary-foreground");
    expect(merged).not.toMatch(/\bbg-primary\b/);
  });
});

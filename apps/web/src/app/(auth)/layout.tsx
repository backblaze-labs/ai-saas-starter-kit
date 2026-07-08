import Link from "next/link";
import { APP_NAME } from "@/lib/app-config";

// Minimal, chrome-free shell for the public auth screens (sign in / sign up).
export default function AuthLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted/30 px-4 py-12">
      <Link
        href="/"
        className="mb-8 flex items-center gap-2.5 font-semibold text-[15px] tracking-tight"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-foreground font-display text-[13px] font-bold text-background">
          B2
        </div>
        <span>{APP_NAME}</span>
      </Link>
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}

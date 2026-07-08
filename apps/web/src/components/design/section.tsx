import type { ReactNode } from "react";

interface SectionProps {
  id: string;
  title: string;
  description?: string;
  children: ReactNode;
}

export function Section({ id, title, description, children }: SectionProps) {
  return (
    <section id={id} className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {description && (
          <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}

export function Row({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[160px_1fr] items-center gap-4 py-2 border-b border-border last:border-b-0">
      <span className="text-xs font-mono text-muted-foreground">{label}</span>
      <div>{children}</div>
    </div>
  );
}

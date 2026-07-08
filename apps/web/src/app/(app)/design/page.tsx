import { DesignTokens } from "@/components/design/design-tokens";
import { DesignPrimitives } from "@/components/design/design-primitives";
import { DesignPatterns } from "@/components/design/design-patterns";
import { DesignAI } from "@/components/design/design-ai";
import { DesignLoader } from "@/components/design/design-loader";

export default function DesignPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Design System</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Every token, primitive, AI element, and pattern in this starter. Use
          this page as a living style guide as the kit grows.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2 space-y-12">
        <DesignTokens />
        <DesignPrimitives />
        <DesignAI />
        <DesignLoader />
        <DesignPatterns />
      </div>
    </div>
  );
}

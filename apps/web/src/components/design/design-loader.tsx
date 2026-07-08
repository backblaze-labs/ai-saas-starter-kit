import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GeneratingLoader } from "@/components/ui/generating-loader";
import { Section } from "./section";

// Showcase for the blaze GeneratingLoader. Tiles use `bg-muted` (not the
// card background) so the white sparkle in the `stars` variant has enough
// contrast to register on light themes — the white-sparkle drop-shadow
// stroke is intentionally subtle and disappears on pure-white surfaces.
export function DesignLoader() {
  return (
    <Section
      id="loader"
      title="Generating loader"
      description="Brand-tinted blaze loader for AI generation states. Perforated dot ring + a flames or stars center. Sized for inline (sm), tile (md), or canvas (lg)."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">sm — inline (button)</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <button
              type="button"
              disabled
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
            >
              <GeneratingLoader size="sm" />
              Generating...
            </button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">md — tile placeholder</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="flex items-center justify-center w-full aspect-video rounded-md bg-muted">
              <GeneratingLoader size="md" />
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">lg — canvas with label</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="flex items-center justify-center rounded-xl border border-border bg-muted aspect-video">
              <GeneratingLoader size="lg" label="Calling the model..." />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">variant=&quot;stars&quot; — md</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="flex items-center justify-center w-full aspect-video rounded-md bg-muted">
              <GeneratingLoader size="md" variant="stars" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">variant=&quot;stars&quot; — lg + label</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="flex items-center justify-center w-full aspect-video rounded-md bg-muted">
              <GeneratingLoader size="lg" variant="stars" label="Refining..." />
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">md over scrim — iterating on existing content</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="relative w-full overflow-hidden rounded-lg aspect-video bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900">
              <div className="absolute inset-0 flex items-center justify-center blaze-scrim">
                <GeneratingLoader size="md" label="Refining..." />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}

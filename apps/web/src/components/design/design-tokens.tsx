import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Section, Row } from "./section";

const colors = [
  { name: "background", var: "--background" },
  { name: "foreground", var: "--foreground" },
  { name: "primary", var: "--primary" },
  { name: "muted", var: "--muted" },
  { name: "muted-foreground", var: "--muted-foreground" },
  { name: "border", var: "--border" },
  { name: "accent-subtle", var: "--accent-subtle" },
  { name: "success", var: "--success" },
  { name: "attention", var: "--attention" },
  { name: "destructive", var: "--destructive" },
];

const radii = [
  { name: "radius-sm", var: "--radius-sm" },
  { name: "radius-md", var: "--radius-md" },
  { name: "radius-lg", var: "--radius-lg" },
  { name: "radius-xl", var: "--radius-xl" },
];

const shadows = [
  { name: "shadow-small", var: "--shadow-small" },
  { name: "shadow-medium", var: "--shadow-medium" },
  { name: "shadow-large", var: "--shadow-large" },
  { name: "shadow-xl", var: "--shadow-xl" },
];

const motion = [
  { name: "duration-short", var: "--duration-short" },
  { name: "duration-medium", var: "--duration-medium" },
  { name: "duration-long", var: "--duration-long" },
  { name: "ease-productive", var: "--ease-productive" },
  { name: "ease-expressive", var: "--ease-expressive" },
];

const type = [
  { label: "Page title — 26px Mona Sans 600", className: "page-title" },
  { label: "Card title — 16px Mona Sans 600", className: "card-title" },
  { label: "Body — 15px regular", className: "text-base" },
  { label: "Small — 13px", className: "text-sm" },
  { label: "Caption — 12px muted", className: "text-xs text-muted-foreground" },
  { label: "Mono — size values", className: "font-mono text-xs tabular-nums" },
];

export function DesignTokens() {
  return (
    <Section
      id="tokens"
      title="Tokens"
      description="Colors, radii, shadows, motion, typography."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Colors</CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            {colors.map((c) => (
              <Row key={c.var} label={c.name}>
                <div className="flex items-center gap-3">
                  <div
                    className="h-6 w-6 rounded border border-border"
                    style={{ background: `var(${c.var})` }}
                  />
                  <span className="font-mono text-xs text-muted-foreground">
                    var({c.var})
                  </span>
                </div>
              </Row>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Radii</CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            {radii.map((r) => (
              <Row key={r.var} label={r.name}>
                <div
                  className="h-8 w-16 bg-accent border border-border"
                  style={{ borderRadius: `var(${r.var})` }}
                />
              </Row>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Elevation</CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            {shadows.map((s) => (
              <Row key={s.var} label={s.name}>
                <div
                  className="h-10 w-24 rounded-md bg-card border border-border"
                  style={{ boxShadow: `var(${s.var})` }}
                />
              </Row>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Motion</CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            {motion.map((m) => (
              <Row key={m.var} label={m.name}>
                <span className="font-mono text-xs text-muted-foreground">
                  var({m.var})
                </span>
              </Row>
            ))}
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Typography</CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            {type.map((t) => (
              <Row key={t.label} label={t.label.split("—")[0].trim()}>
                <p className={t.className}>{t.label}</p>
              </Row>
            ))}
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}

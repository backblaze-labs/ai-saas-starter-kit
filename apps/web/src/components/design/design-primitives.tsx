"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Section } from "./section";
import { Info } from "lucide-react";

export function DesignPrimitives() {
  const [progress, setProgress] = useState(40);

  return (
    <Section
      id="primitives"
      title="Primitives"
      description="Every shadcn/ui component available in the starter, live."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Buttons</CardTitle>
          </CardHeader>
          <CardContent className="p-5 flex flex-wrap gap-2">
            <Button>Primary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="secondary">Secondary</Button>
            <Button size="sm">Small</Button>
            <Button size="icon" aria-label="icon">
              <Info />
            </Button>
            <Button disabled>Disabled</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Badges</CardTitle>
          </CardHeader>
          <CardContent className="p-5 flex flex-wrap gap-2">
            <Badge>Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="outline">Outline</Badge>
            <Badge variant="destructive">Destructive</Badge>
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
              Status dot
            </span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Form controls
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="demo-input">Text input</Label>
              <Input id="demo-input" placeholder="type here" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="demo-area">Textarea</Label>
              <Textarea id="demo-area" placeholder="multi-line" rows={2} />
            </div>
            <div className="flex items-center gap-3">
              <Checkbox id="demo-check" />
              <Label htmlFor="demo-check">Checkbox</Label>
            </div>
            <div className="flex items-center gap-3">
              <Switch id="demo-switch" />
              <Label htmlFor="demo-switch">Switch</Label>
            </div>
            <RadioGroup defaultValue="a" className="flex gap-4">
              {["a", "b", "c"].map((v) => (
                <label key={v} className="flex items-center gap-1.5 text-sm">
                  <RadioGroupItem value={v} />
                  Option {v}
                </label>
              ))}
            </RadioGroup>
            <Select defaultValue="one">
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="one">Option one</SelectItem>
                <SelectItem value="two">Option two</SelectItem>
                <SelectItem value="three">Option three</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Feedback</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <Alert>
              <Info />
              <AlertTitle>Informational</AlertTitle>
              <AlertDescription>
                Alerts persist until dismissed — use for announcements.
              </AlertDescription>
            </Alert>
            <Progress value={progress} className="progress-gradient" />
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setProgress((p) => Math.max(0, p - 10))}
              >
                -10
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setProgress((p) => Math.min(100, p + 10))}
              >
                +10
              </Button>
            </div>
            <div className="space-y-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-24" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Overlays</CardTitle>
          </CardHeader>
          <CardContent className="p-5 flex flex-wrap gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" size="sm">
                  Hover me
                </Button>
              </TooltipTrigger>
              <TooltipContent>Tooltip content</TooltipContent>
            </Tooltip>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm">
                  Popover
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-56">
                <p className="text-sm">Arbitrary content inside a popover.</p>
              </PopoverContent>
            </Popover>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Disclosure &amp; navigation
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <Tabs defaultValue="one">
              <TabsList>
                <TabsTrigger value="one">Tab one</TabsTrigger>
                <TabsTrigger value="two">Tab two</TabsTrigger>
              </TabsList>
              <TabsContent value="one" className="pt-3 text-sm">
                Content for tab one.
              </TabsContent>
              <TabsContent value="two" className="pt-3 text-sm">
                Content for tab two.
              </TabsContent>
            </Tabs>
            <Separator />
            <Accordion type="single" collapsible>
              <AccordionItem value="a">
                <AccordionTrigger>Question one</AccordionTrigger>
                <AccordionContent>
                  Accordion bodies expand on click.
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="b">
                <AccordionTrigger>Question two</AccordionTrigger>
                <AccordionContent>
                  Only one panel open at a time.
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Identity &amp; chrome
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 flex items-center gap-4">
            <Avatar>
              <AvatarFallback>JD</AvatarFallback>
            </Avatar>
            <Separator orientation="vertical" className="h-8" />
            <kbd className="text-[10px] font-mono border border-border rounded px-1.5 py-0.5 text-muted-foreground">
              ⌘K
            </kbd>
            <span className="text-xs text-muted-foreground">
              Keyboard hint convention
            </span>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}

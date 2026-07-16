"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Lock, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth/auth-provider";
import { ApiError } from "@/lib/api-client";
import {
  useEntitlements,
  useGenerate,
  useGenerationJobs,
  usePreviewUrl,
} from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { GeneratingLoader } from "@/components/ui/generating-loader";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { GeneratedAsset, GenerationJob } from "@ai-saas-starter-kit/shared";

const UNAVAILABLE_MSG =
  "Image generation is temporarily unavailable. Please try again later.";

function generateErrorToast(err: ApiError) {
  if (err.status === 503) toast.error(UNAVAILABLE_MSG);
  else if (err.status === 402) toast.error("Upgrade to Pro to generate media.");
  else toast.error("Something went wrong. Please try again.");
}

// One generated image, fetched via a short-lived presigned preview URL by its
// B2 key — the same path the file manager uses, so it renders whether or not
// B2_PUBLIC_URL_BASE is set (a private bucket still works).
function GeneratedImage({ asset }: { asset: GeneratedAsset }) {
  const { data, isLoading } = usePreviewUrl(asset.key, true);
  const url = data?.url ?? asset.url ?? null;
  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-lg border bg-muted/30">
      {isLoading || !url ? (
        <Skeleton className="h-full w-full" />
      ) : (
        <Image
          src={url}
          alt="Generated image"
          fill
          sizes="(max-width: 768px) 100vw, 320px"
          className="object-cover"
          // presigned URLs carry their own expiry — don't let Next cache past it
          unoptimized
        />
      )}
    </div>
  );
}

function LockedCard() {
  return (
    <Card data-testid="generate-locked">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Lock className="h-5 w-5 text-muted-foreground" />
          <CardTitle>AI media generation is a Pro feature</CardTitle>
        </div>
        <CardDescription>
          AI media generation is available on the Pro and Team plans. Upgrade to
          unlock it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link href="/billing">View plans</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function statusVariant(status: string): "default" | "secondary" | "destructive" {
  if (status === "succeeded") return "default";
  if (status === "failed") return "destructive";
  return "secondary";
}

function JobCard({ job }: { job: GenerationJob }) {
  const asset = job.assets[0];
  return (
    <Card data-testid="generate-job">
      {asset ? (
        <GeneratedImage asset={asset} />
      ) : (
        <div className="flex aspect-square w-full items-center justify-center rounded-lg border bg-muted/30 text-xs text-muted-foreground">
          No image
        </div>
      )}
      <CardContent className="space-y-2 pt-4">
        <p className="line-clamp-2 text-sm" title={job.prompt}>
          {job.prompt}
        </p>
        <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
      </CardContent>
    </Card>
  );
}

export default function GeneratePage() {
  const { user } = useAuth();
  const enabled = !!user;
  const entitlements = useEntitlements(enabled);
  const jobs = useGenerationJobs(enabled);
  const generate = useGenerate();

  const [prompt, setPrompt] = useState("");
  const [seed, setSeed] = useState("");
  const [latest, setLatest] = useState<GenerationJob | null>(null);

  const canGenerate = entitlements.data?.can_generate ?? false;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (trimmed.length === 0) return;
    const parsedSeed = seed.trim() === "" ? null : Number.parseInt(seed, 10);
    generate.mutate(
      { prompt: trimmed, seed: Number.isFinite(parsedSeed) ? parsedSeed : null },
      {
        onSuccess: (job) => {
          setLatest(job);
          toast.success("Image generated and saved to B2.");
        },
        onError: generateErrorToast,
      },
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="border-b border-border pb-5">
        <h1 className="page-title flex items-center gap-2">
          <Wand2 className="h-6 w-6" />
          Generate
        </h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground text-pretty">
          Describe an image and we&apos;ll generate it and save it to your
          Backblaze B2 storage. It appears here and in your files.
        </p>
      </header>

      {entitlements.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : !canGenerate ? (
        <LockedCard />
      ) : (
        <>
          <Card>
            <CardContent className="pt-6">
              <form onSubmit={onSubmit} data-testid="generate-form" className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="prompt">Prompt</Label>
                  <Textarea
                    id="prompt"
                    data-testid="generate-prompt"
                    placeholder="A serene mountain lake at golden hour, photorealistic"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    rows={3}
                    maxLength={2000}
                    disabled={generate.isPending}
                  />
                </div>
                <div className="flex flex-wrap items-end gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="seed">Seed (optional)</Label>
                    <Input
                      id="seed"
                      data-testid="generate-seed"
                      type="number"
                      min={0}
                      placeholder="random"
                      value={seed}
                      onChange={(e) => setSeed(e.target.value)}
                      disabled={generate.isPending}
                      className="w-40"
                    />
                  </div>
                  <Button
                    type="submit"
                    data-testid="generate-submit"
                    disabled={generate.isPending || prompt.trim().length === 0}
                  >
                    {generate.isPending ? "Generating…" : "Generate"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {generate.isPending && (
            <div
              className="flex flex-col items-center gap-3 py-8"
              data-testid="generate-loading"
            >
              <GeneratingLoader size="lg" variant="stars" />
              <p className="text-sm text-muted-foreground">
                Generating your image…
              </p>
            </div>
          )}

          {latest && latest.assets.length > 0 && (
            <div data-testid="generate-result" className="space-y-3">
              <h2 className="text-sm font-semibold">Latest result</h2>
              <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
                {latest.assets.map((asset) => (
                  <GeneratedImage key={asset.key} asset={asset} />
                ))}
              </div>
            </div>
          )}

          <div className="space-y-3">
            <h2 className="text-sm font-semibold">Recent generations</h2>
            {jobs.isPending ? (
              <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
                <Skeleton className="h-64" />
                <Skeleton className="h-64" />
                <Skeleton className="h-64" />
              </div>
            ) : jobs.data && jobs.data.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
                {jobs.data.map((job) => (
                  <JobCard key={job.id} job={job} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No generations yet — describe an image above to create your first.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

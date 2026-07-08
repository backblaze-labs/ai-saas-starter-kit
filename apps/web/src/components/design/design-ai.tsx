"use client";

import { Bot, MessageSquare, Wand2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Section } from "./section";

/**
 * AI design elements — neutral primitives for building a chat or
 * assistant surface. Implementors can re-skin with their own brand.
 */
export function DesignAI() {
  return (
    <Section
      id="ai"
      title="AI elements"
      description="Primitives for chat / assistant surfaces. Compose them into a drawer, inline panel, or whatever fits your product — we intentionally don't ship a dummy assistant."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Chat thread</CardTitle>
          </CardHeader>
          <CardContent className="p-5 flex flex-col gap-3">
            <div className="flex items-start gap-2 animate-bubble-in">
              <span className="ai-avatar h-7 w-7 shrink-0">
                <Bot className="h-3.5 w-3.5" />
              </span>
              <div className="chat-bubble assistant">
                Hi — I can help you search your bucket, summarize activity,
                or draft storage policies. What&apos;s on your mind?
              </div>
            </div>
            <div className="flex justify-end animate-bubble-in">
              <div className="chat-bubble user">
                Summarize my storage usage this week.
              </div>
            </div>
            <div className="flex items-start gap-2 animate-bubble-in">
              <span className="ai-avatar h-7 w-7 shrink-0">
                <Bot className="h-3.5 w-3.5" />
              </span>
              <div className="chat-bubble assistant">
                <span className="chat-typing">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Suggested prompts</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <p className="text-xs text-muted-foreground">
              Use <code className="font-mono text-[11px]">.prompt-chip</code>{" "}
              for clickable starter questions in an empty chat state.
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="prompt-chip">
                <Wand2 className="h-3.5 w-3.5" />
                Summarize this bucket
              </span>
              <span className="prompt-chip">
                <MessageSquare className="h-3.5 w-3.5" />
                Explain presigned URLs
              </span>
              <span className="prompt-chip">
                <Bot className="h-3.5 w-3.5" />
                Draft a lifecycle rule
              </span>
            </div>
            <p className="text-xs text-muted-foreground pt-2">
              The AI avatar uses <code className="font-mono text-[11px]">.ai-avatar</code>{" "}
              — a solid accent-blue disc. Swap the icon or color to match
              your assistant&apos;s identity.
            </p>
            <div className="flex items-center gap-3">
              <span className="ai-avatar">
                <Bot className="h-3.5 w-3.5" />
              </span>
              <span className="ai-avatar">
                <Wand2 className="h-3.5 w-3.5" />
              </span>
              <span className="ai-avatar">
                <MessageSquare className="h-3.5 w-3.5" />
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}

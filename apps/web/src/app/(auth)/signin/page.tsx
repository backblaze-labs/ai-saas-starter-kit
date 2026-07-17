"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { safeNextPath } from "@/lib/safe-redirect";

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <Card className="card-standard">
          <CardHeader>
            <CardTitle>Sign in</CardTitle>
            <CardDescription>Welcome back.</CardDescription>
          </CardHeader>
        </Card>
      }
    >
      <SignInInner />
    </Suspense>
  );
}

function SignInInner() {
  const supabase = createClient();
  const searchParams = useSearchParams();
  const next = safeNextPath(searchParams.get("next"));
  const [error, setError] = useState<string | null>(null);
  const shownError =
    error ??
    (searchParams.get("error") === "confirmation-failed"
      ? "That confirmation link is invalid or expired. Try signing in or sign up again."
      : null);

  return (
    <Card className="card-standard">
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>Welcome back.</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="password">
          <TabsList className="mb-4 grid w-full grid-cols-2">
            <TabsTrigger value="password">Password</TabsTrigger>
            <TabsTrigger value="otp">Email code</TabsTrigger>
          </TabsList>
          <TabsContent value="password">
            <PasswordForm supabase={supabase} next={next} onError={setError} />
          </TabsContent>
          <TabsContent value="otp">
            <OtpForm supabase={supabase} next={next} onError={setError} />
          </TabsContent>
        </Tabs>

        {shownError && (
          <p role="alert" className="mt-4 text-sm text-destructive">
            {shownError}
          </p>
        )}

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="font-medium text-foreground underline">
            Sign up
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

type FormProps = {
  supabase: ReturnType<typeof createClient>;
  next: string;
  onError: (msg: string | null) => void;
};

function PasswordForm({ supabase, next, onError }: FormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onError(null);
    setSubmitting(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setSubmitting(false);
    if (error) {
      onError(error.message);
      return;
    }
    window.location.assign(next);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="pw-email">Email</Label>
        <Input
          id="pw-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="pw-password">Password</Label>
        <Input
          id="pw-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}

function OtpForm({ supabase, next, onError }: FormProps) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState<"email" | "code">("email");
  const [submitting, setSubmitting] = useState(false);

  async function requestCode(e: React.FormEvent) {
    e.preventDefault();
    onError(null);
    setSubmitting(true);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: false },
    });
    setSubmitting(false);
    if (error) {
      onError(error.message);
      return;
    }
    setStage("code");
  }

  async function verifyCode(e: React.FormEvent) {
    e.preventDefault();
    onError(null);
    setSubmitting(true);
    const { error } = await supabase.auth.verifyOtp({ email, token: code, type: "email" });
    setSubmitting(false);
    if (error) {
      onError(error.message);
      return;
    }
    window.location.assign(next);
  }

  if (stage === "code") {
    return (
      <form onSubmit={verifyCode} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="otp-code">6-digit code</Label>
          <Input
            id="otp-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="123456"
          />
          <p className="text-xs text-muted-foreground">We emailed a code to {email}.</p>
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Verifying…" : "Verify & sign in"}
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={requestCode} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="otp-email">Email</Label>
        <Input
          id="otp-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
      </div>
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Sending…" : "Email me a code"}
      </Button>
    </form>
  );
}

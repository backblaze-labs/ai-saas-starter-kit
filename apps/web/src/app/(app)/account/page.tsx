"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth/auth-provider";
import { createClient } from "@/lib/supabase/client";
import { useMe } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function AccountPage() {
  const { user, profile, isAdmin, signOut, refreshProfile } = useAuth();
  const supabase = createClient();
  // `null` draft means "untouched" — fall back to the loaded profile value so
  // the input reflects the profile without a sync-state-in-effect.
  const [fullNameDraft, setFullNameDraft] = useState<string | null>(null);
  const fullName = fullNameDraft ?? profile?.full_name ?? "";
  const [saving, setSaving] = useState(false);
  const me = useMe(!!user);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    setSaving(true);
    const { error } = await supabase
      .from("profiles")
      .update({ full_name: fullName })
      .eq("id", user.id);
    setSaving(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    await refreshProfile();
    toast.success("Profile updated");
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Account</h1>
        <p className="text-sm text-muted-foreground">Manage your profile and session.</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Profile</CardTitle>
              <CardDescription>{user?.email}</CardDescription>
            </div>
            <Badge variant={isAdmin ? "default" : "secondary"}>{profile?.role ?? "user"}</Badge>
          </div>
        </CardHeader>
        <form onSubmit={saveProfile}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={user?.email ?? ""} disabled />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fullName">Full name</Label>
              <Input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullNameDraft(e.target.value)}
                placeholder="Your name"
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API session</CardTitle>
          <CardDescription>
            Confirms the FastAPI backend accepts your Supabase access token.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {me.isPending ? (
            <p className="text-sm text-muted-foreground">Checking…</p>
          ) : me.isError ? (
            <p className="text-sm text-muted-foreground">
              Backend did not validate the session (is the API running?).
            </p>
          ) : (
            <p className="text-sm">
              Authenticated to the API as{" "}
              <span className="font-medium">{me.data?.email}</span> (role{" "}
              <span className="font-medium">{me.data?.role}</span>).
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
          <CardDescription>Sign out of this device.</CardDescription>
        </CardHeader>
        <CardFooter>
          <Button variant="outline" onClick={() => void signOut()}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign out
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

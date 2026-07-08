"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";

export type Profile = {
  id: string;
  email: string | null;
  full_name: string | null;
  avatar_url: string | null;
  role: string;
};

type AuthState = {
  user: User | null;
  profile: Profile | null;
  isAdmin: boolean;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({
  children,
  initialUser,
}: {
  children: ReactNode;
  initialUser: User | null;
}) {
  const supabase = useMemo(() => createClient(), []);
  const router = useRouter();
  const [user, setUser] = useState<User | null>(initialUser);
  const [profile, setProfile] = useState<Profile | null>(null);

  // Keep the client user in sync with auth events (sign in/out, token refresh).
  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  // Load the profile row (RLS scopes this to the current user). Only the async
  // fetch touches state here; clearing on sign-out is handled by masking below,
  // so no synchronous setState runs in the effect body.
  useEffect(() => {
    if (!user) return;
    let active = true;
    void supabase
      .from("profiles")
      .select("id, email, full_name, avatar_url, role")
      .eq("id", user.id)
      .single()
      .then(({ data }) => {
        if (active) setProfile((data as Profile) ?? null);
      });
    return () => {
      active = false;
    };
  }, [user, supabase]);

  // The profile in state may lag a sign-out for one tick; never expose a stale
  // profile once the user is gone.
  const effectiveProfile = user ? profile : null;

  const value = useMemo<AuthState>(
    () => ({
      user,
      profile: effectiveProfile,
      isAdmin: effectiveProfile?.role === "admin",
      async signOut() {
        await supabase.auth.signOut();
        router.replace("/signin");
        router.refresh();
      },
      async refreshProfile() {
        if (!user) return;
        const { data } = await supabase
          .from("profiles")
          .select("id, email, full_name, avatar_url, role")
          .eq("id", user.id)
          .single();
        setProfile((data as Profile) ?? null);
      },
    }),
    [user, effectiveProfile, supabase, router],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

import { createBrowserClient } from "@supabase/ssr";

/**
 * Browser-side Supabase client. Reads the public URL + anon key (safe to expose).
 * `createBrowserClient` returns a cached singleton per key, so calling this in
 * multiple components is fine.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}

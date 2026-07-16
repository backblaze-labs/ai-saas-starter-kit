import { type EmailOtpType } from "@supabase/supabase-js";
import { type NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { safeNextPath } from "@/lib/safe-redirect";

// Landing point for email confirmation / magic links. Supabase's email link can
// arrive in either of two shapes depending on the project's email template, so we
// handle both and this route works local or hosted:
//   - `?code=…`            PKCE flow, produced by the default `{{ .ConfirmationURL }}`
//                          template (what hosted projects that can't customize
//                          templates on the free tier send) — exchanged for a session.
//   - `?token_hash=&type=` the SSR `verifyOtp` template (the local custom template).
// Either way, a successful verify sets the session cookies, then we redirect in.
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = safeNextPath(searchParams.get("next"));

  const supabase = await createClient();

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(next, request.url));
    }
  } else if (token_hash && type) {
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    if (!error) {
      return NextResponse.redirect(new URL(next, request.url));
    }
  }

  const failed = new URL("/signin", request.url);
  failed.searchParams.set("error", "confirmation-failed");
  return NextResponse.redirect(failed);
}

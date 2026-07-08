import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

// Next 16 renamed the `middleware` file convention to `proxy`. This runs on every
// request to refresh the Supabase session cookies and enforce route protection.
export async function proxy(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  // Run on every path except Next internals and static assets. Auth exemptions
  // for /signin, /signup, /auth/* are handled inside updateSession.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};

/**
 * Return `next` only if it is a safe same-site *relative* path, else "/".
 *
 * Rejects anything that a browser could resolve to another origin:
 *  - not starting with "/"           (absolute URLs, "javascript:", etc.)
 *  - starting with "//"              (protocol-relative -> //evil.com)
 *  - containing a backslash          ("/\evil.com" resolves to http://evil.com)
 *
 * Used by the sign-in `next` param, the /auth/confirm handler, and the proxy so
 * an attacker cannot craft a post-auth open redirect.
 */
export function safeNextPath(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) {
    return "/";
  }
  return next;
}

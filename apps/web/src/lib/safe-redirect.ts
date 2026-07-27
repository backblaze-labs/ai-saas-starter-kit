// C0 control chars + DEL (tab, newline, CR and friends). The WHATWG URL parser
// strips tab/newline/CR *before* resolving, so a value like "/\n/evil.com" would
// slip past a naive "starts with /" guard and then resolve cross-origin. Reject
// any value containing one rather than trying to strip-then-revalidate.
const CONTROL_CHARS_RE = /[\x00-\x1f\x7f]/;

/**
 * Return `next` only if it is a safe same-site *relative* path, else "/".
 *
 * Rejects anything that a browser could resolve to another origin:
 *  - not starting with "/"           (absolute URLs, "javascript:", etc.)
 *  - starting with "//"              (protocol-relative -> //evil.com)
 *  - containing a backslash          ("/\evil.com" resolves to http://evil.com)
 *  - containing a control char       ("/\n/evil.com" -> the URL parser drops the
 *                                     newline, leaving "//evil.com" cross-origin)
 *
 * Used by the sign-in `next` param, the /auth/confirm handler, and the proxy so
 * an attacker cannot craft a post-auth open redirect.
 */
export function safeNextPath(next: string | null | undefined): string {
  if (
    !next ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next.includes("\\") ||
    CONTROL_CHARS_RE.test(next)
  ) {
    return "/";
  }
  return next;
}

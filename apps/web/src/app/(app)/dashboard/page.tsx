import { redirect } from "next/navigation";

// The dashboard lives at "/" (see app/(app)/page.tsx). This alias keeps the
// conventional /dashboard URL working and protected (the (app) group requires a
// session via middleware).
export default function DashboardAlias() {
  redirect("/");
}

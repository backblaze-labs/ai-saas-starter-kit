import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Header } from "@/components/layout/header";
import { HealthBanner } from "@/components/layout/health-banner";
import { RefreshProvider } from "@/lib/refresh-context";
import { AuthProvider } from "@/components/auth/auth-provider";
import { createClient } from "@/lib/supabase/server";

// Authenticated app shell. The middleware already guarantees a session before any
// route in this group renders, but we resolve the user here too so the initial
// paint has it (no auth flash) and pass it to the client-side AuthProvider.
export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <AuthProvider initialUser={user}>
      <RefreshProvider>
        <SidebarProvider>
          <TooltipProvider>
            <AppSidebar />
            <div className="flex flex-1 flex-col">
              <Header />
              <HealthBanner />
              <main className="flex-1 overflow-auto p-6 lg:p-8">{children}</main>
            </div>
          </TooltipProvider>
        </SidebarProvider>
      </RefreshProvider>
    </AuthProvider>
  );
}

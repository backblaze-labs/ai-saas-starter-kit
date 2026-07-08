import type { Metadata } from "next";
import { Mona_Sans } from "next/font/google";
import "./globals.css";

import { ThemeProvider } from "@/components/layout/theme-provider";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Header } from "@/components/layout/header";
import { HealthBanner } from "@/components/layout/health-banner";
import { Toaster } from "@/components/ui/sonner";
import { QueryClientProvider } from "@/lib/query-client";
import { RefreshProvider } from "@/lib/refresh-context";
import { APP_NAME, APP_DESCRIPTION } from "@/lib/app-config";

// Display face — used for page titles. Body copy uses the system stack
// defined in globals.css.
const monaSans = Mona_Sans({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: APP_NAME,
  description: APP_DESCRIPTION,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body className={`${monaSans.variable} antialiased`}>
        <ThemeProvider>
          <QueryClientProvider>
            <RefreshProvider>
              <SidebarProvider>
                <TooltipProvider>
                  <AppSidebar />
                  <div className="flex flex-1 flex-col">
                    <Header />
                    <HealthBanner />
                    <main className="flex-1 overflow-auto p-6 lg:p-8">
                      {children}
                    </main>
                  </div>
                  <Toaster />
                </TooltipProvider>
              </SidebarProvider>
            </RefreshProvider>
          </QueryClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

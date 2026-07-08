"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Upload,
  FolderOpen,
  Settings,
  Sparkles,
  UserRound,
  CreditCard,
  Wand2,
  LogOut,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
} from "@/components/ui/sidebar";
import { APP_NAME } from "@/lib/app-config";
import { useAuth } from "@/components/auth/auth-provider";

const navItems = [
  { title: "Dashboard", href: "/", icon: LayoutDashboard },
  { title: "Generate", href: "/generate", icon: Wand2 },
  { title: "Upload", href: "/upload", icon: Upload },
  { title: "Files", href: "/files", icon: FolderOpen },
  { title: "Billing", href: "/billing", icon: CreditCard },
  { title: "Account", href: "/account", icon: UserRound },
  { title: "Settings", href: "/settings", icon: Settings },
];

const utilItems = [{ title: "Design System", href: "/design", icon: Sparkles }];

export function AppSidebar() {
  const pathname = usePathname();
  const { user, profile, signOut } = useAuth();

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border px-4 py-3.5">
        <Link
          href="/"
          className="flex items-center gap-2.5 font-semibold text-[15px] tracking-tight"
        >
          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-foreground text-background font-display font-bold text-[13px]">
            B2
          </div>
          <span>{APP_NAME}</span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      className={
                        isActive
                          ? "relative font-semibold before:content-[''] before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:h-5 before:w-[3px] before:rounded-r-full before:bg-primary"
                          : ""
                      }
                    >
                      <Link href={item.href}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Reference
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {utilItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      className={
                        isActive
                          ? "relative font-semibold before:content-[''] before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:h-5 before:w-[3px] before:rounded-r-full before:bg-primary"
                          : ""
                      }
                    >
                      <Link href={item.href}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="gap-2 border-t border-sidebar-border px-4 py-3">
        {user && (
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium">{user.email}</p>
              {profile?.role && (
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  {profile.role}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => void signOut()}
              aria-label="Sign out"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
        <a
          href="https://www.backblaze.com/cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-ai-media-saas-starter"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#e42c39]" />
          Built on Backblaze B2
        </a>
      </SidebarFooter>
    </Sidebar>
  );
}

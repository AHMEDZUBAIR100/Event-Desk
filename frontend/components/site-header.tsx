"use client";

import { ChevronDown, Menu, Ticket } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatRole, getInitials } from "@/lib/format";
import { cn } from "@/lib/utils";

const navigation = [{ href: "/events", label: "Browse events" }];

function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <Link
      href="/events"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-sm text-sm font-semibold tracking-tight"
    >
      <span className="grid h-6 w-6 place-items-center rounded-sm bg-foreground text-background">
        <Ticket className="h-3.5 w-3.5" />
      </span>
      EventDesk
    </Link>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-2">
          <span className="grid h-7 w-7 place-items-center rounded-full border border-border text-[11px] font-medium">
            {getInitials(user.full_name)}
          </span>
          <span className="hidden max-w-32 truncate text-sm sm:block">
            {user.full_name}
          </span>
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate text-sm font-medium">
            {user.full_name}
          </span>
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
            {user.email}
          </span>
          <span className="mt-2 block text-xs text-muted-foreground">
            {formatRole(user.role)}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logout()}>
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function AuthActions({ onNavigate }: { onNavigate?: () => void }) {
  const { user, status } = useAuth();

  if (status === "loading") {
    return <div className="h-9 w-24 animate-pulse rounded-md bg-muted" />;
  }

  if (user) {
    return <UserMenu />;
  }

  return (
    <div className="flex items-center gap-2">
      <Button variant="ghost" size="sm" asChild>
        <Link href="/login" onClick={onNavigate}>
          Sign in
        </Link>
      </Button>
      <Button size="sm" asChild>
        <Link href="/register" onClick={onNavigate}>
          Create account
        </Link>
      </Button>
    </div>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="border-b">
      <div className="container flex h-16 max-w-[1120px] items-center justify-between gap-4">
        <div className="flex items-center gap-8">
          <Brand />
          <nav className="hidden items-center gap-6 md:flex">
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "text-sm text-muted-foreground transition-colors hover:text-foreground",
                  pathname.startsWith(item.href) && "text-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-1 sm:gap-2">
          <ThemeToggle />
          <div className="hidden md:block">
            <AuthActions />
          </div>

          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden"
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[300px]">
              <SheetHeader>
                <SheetTitle className="text-left">
                  <Brand onClick={() => setMobileOpen(false)} />
                </SheetTitle>
              </SheetHeader>
              <nav className="mt-8 flex flex-col gap-1">
                {navigation.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
              <div className="mt-8 border-t pt-6">
                <AuthActions onNavigate={() => setMobileOpen(false)} />
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BookOpenText, Library, LogOut, Upload } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe, type Me } from "@/hooks/use-me";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/library", label: "Thư viện", icon: Library },
  { href: "/upload", label: "Tải lên", icon: Upload },
];

function UserMenu({ me }: { me: Me }) {
  const qc = useQueryClient();
  const router = useRouter();

  async function logout() {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } finally {
      qc.clear();
      router.replace("/");
    }
  }

  const initials = me.name
    .split(/\s+/)
    .map((w) => w[0])
    .slice(-2)
    .join("")
    .toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="ghost" size="icon" className="rounded-full" />}
        aria-label="Tài khoản"
      >
        <Avatar>
          {me.avatar_url && <AvatarImage src={me.avatar_url} alt={me.name} />}
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            <div className="truncate font-medium text-foreground">{me.name}</div>
            <div className="truncate text-xs font-normal">{me.email}</div>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout}>
          <LogOut /> Đăng xuất
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Khung trang sau đăng nhập; `/me` trả 401 → về trang chủ (ADR-0005). */
export function AppShell({ children }: { children: ReactNode }) {
  const { data: me, isPending, isError } = useMe();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isPending && me === null) router.replace("/");
  }, [isPending, me, router]);

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-4">
          <Link href="/library" className="mr-2 flex items-center gap-2 font-semibold">
            <BookOpenText className="size-5 text-primary" />
            <span>Stugen</span>
          </Link>
          <nav className="flex items-center gap-1">
            {NAV.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  buttonVariants({ variant: "ghost", size: "sm" }),
                  pathname.startsWith(href) && "bg-muted",
                )}
              >
                <Icon /> <span className="hidden sm:inline">{label}</span>
              </Link>
            ))}
          </nav>
          <div className="ml-auto">
            {me ? <UserMenu me={me} /> : <Skeleton className="size-8 rounded-full" />}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {isError ? (
          <p className="text-destructive">Không kết nối được máy chủ, vui lòng tải lại trang.</p>
        ) : me ? (
          children
        ) : (
          <div className="space-y-3">
            <Skeleton className="h-8 w-60" />
            <Skeleton className="h-40 w-full" />
          </div>
        )}
      </main>
    </div>
  );
}

"use client";

import { LogIn } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { useMe } from "@/hooks/use-me";

const LOGIN_ERRORS: Record<string, string> = {
  access_denied: "Bạn đã huỷ đăng nhập.",
  invalid_state: "Phiên đăng nhập không hợp lệ, vui lòng thử lại.",
  email_not_verified: "Email Google chưa được xác minh.",
  google_error: "Không đăng nhập được với Google, vui lòng thử lại.",
};

export function LoginErrorNotice() {
  const code = useSearchParams().get("login_error");
  if (!code) return null;
  return (
    <Alert variant="destructive" className="max-w-xl">
      <AlertDescription>{LOGIN_ERRORS[code] ?? LOGIN_ERRORS.google_error}</AlertDescription>
    </Alert>
  );
}

export function HomeActions() {
  const { data: me, isPending } = useMe();

  if (!isPending && me) {
    return (
      <Link href="/library" className={buttonVariants({ size: "lg" })}>
        Vào thư viện của {me.name}
      </Link>
    );
  }
  return (
    // Điều hướng trình duyệt (không fetch) để backend thực hiện OAuth (ADR-0005)
    <a href="/api/auth/google/login" className={buttonVariants({ size: "lg" })}>
      <LogIn /> Đăng nhập với Google
    </a>
  );
}

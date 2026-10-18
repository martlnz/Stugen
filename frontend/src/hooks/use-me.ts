"use client";

import { useQuery } from "@tanstack/react-query";

import { api, ApiError, type Schema } from "@/lib/api";

export type Me = Schema<"MeOut">;

/** Người dùng hiện tại; `null` khi chưa đăng nhập (401). */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<Me | null> => {
      try {
        return await api<Me>("/me");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: 60_000,
  });
}

"use client";

import { Sparkles } from "lucide-react";

import { AiNotice } from "@/components/ai-notice";
import { Markdown } from "@/components/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { useSummary } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";
import { pageRange } from "@/lib/format";

export function SummaryTab({
  lectureId,
  onOpenPage,
}: {
  lectureId: string;
  onOpenPage: (page: number) => void;
}) {
  const { data, isPending, error } = useSummary(lectureId, true);

  if (isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (error) return <p className="text-destructive">{errorMessage(error)}</p>;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_260px]">
      <article className="min-w-0 space-y-4">
        <AiNotice />
        <Markdown>{data.content_md}</Markdown>
      </article>
      <aside className="order-first lg:order-none">
        <div className="rounded-xl border p-4 lg:sticky lg:top-20">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="size-4 text-primary" /> Mục lục
          </h2>
          <ol className="space-y-2 text-sm">
            {data.chapters.map((ch) => (
              <li key={ch.idx}>
                <p className="leading-snug">{ch.title}</p>
                <button
                  type="button"
                  onClick={() => onOpenPage(ch.page_start)}
                  className="text-xs text-primary hover:underline"
                >
                  Xem PDF {pageRange(ch.page_start, ch.page_end)}
                </button>
              </li>
            ))}
          </ol>
        </div>
      </aside>
    </div>
  );
}

"use client";

import { BookMarked, FileText } from "lucide-react";

import { AiNotice } from "@/components/ai-notice";
import { InlineMath } from "@/components/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { useLessonSummary } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";
import { pagesLabel } from "@/lib/format";

/** Tóm tắt một bài: tổng quan, các mục nhỏ kèm trang, thuật ngữ (không có tên file). */
export function SummaryTab({
  lessonId,
  onOpenPage,
}: {
  lessonId: string;
  onOpenPage: (page: number) => void;
}) {
  const { data, isPending, error } = useLessonSummary(lessonId, true);

  if (isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (error) return <p className="text-destructive">{errorMessage(error)}</p>;

  return (
    <article className="space-y-6 text-[15px]">
      <AiNotice />
      <section className="rounded-xl bg-muted/50 p-4 leading-7">
        <h2 className="mb-1 text-sm font-semibold text-muted-foreground">Tổng quan</h2>
        <InlineMath>{data.overview}</InlineMath>
      </section>

      <ol className="space-y-5">
        {data.sections.map((section, i) => (
          <li key={i} className="space-y-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-1">
              <h3 className="font-semibold">
                <span className="mr-1.5 text-muted-foreground">{i + 1}.</span>
                <InlineMath>{section.title}</InlineMath>
              </h3>
              <button
                type="button"
                onClick={() => onOpenPage(section.page_start)}
                className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-xs text-primary hover:bg-primary/20"
              >
                <FileText className="size-3" />
                {pagesLabel(section.page_start, section.page_end)}
              </button>
            </div>
            <ul className="list-disc space-y-1.5 pl-6 leading-7">
              {section.key_points.map((point, k) => (
                <li key={k}>
                  <InlineMath>{point}</InlineMath>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>

      {data.terms.length > 0 && (
        <section>
          <h2 className="mb-2 flex items-center gap-2 font-semibold">
            <BookMarked className="size-4 text-primary" /> Thuật ngữ
          </h2>
          <dl className="grid gap-2 sm:grid-cols-2">
            {data.terms.map((t, i) => (
              <div key={i} className="rounded-lg border p-3 text-sm">
                <dt className="font-semibold">{t.term}</dt>
                <dd className="text-muted-foreground">
                  <InlineMath>{t.definition}</InlineMath>
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </article>
  );
}

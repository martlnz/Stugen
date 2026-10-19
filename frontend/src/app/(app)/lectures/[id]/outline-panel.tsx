"use client";

import { AlertCircle, CheckCircle2, Circle, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useGenerateLessons, type LessonItem, type Outline } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";
import { lessonStepLabel, pagesLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

const SELECTABLE = new Set<LessonItem["status"]>(["pending", "failed"]);

function StatusIcon({ lesson }: { lesson: LessonItem }) {
  switch (lesson.status) {
    case "completed":
      return <CheckCircle2 className="size-4 text-green-600" aria-label="Đã tạo" />;
    case "queued":
    case "processing":
      return <Loader2 className="size-4 animate-spin text-primary" aria-label="Đang tạo" />;
    case "failed":
      return <AlertCircle className="size-4 text-destructive" aria-label="Lỗi" />;
    default:
      return <Circle className="size-4 text-muted-foreground/50" aria-label="Chưa tạo" />;
  }
}

export function OutlinePanel({
  lectureId,
  outline,
  selectedLessonId,
  checked,
  onCheckedChange,
  onOpenLesson,
  onOpenPage,
}: {
  lectureId: string;
  outline: Outline;
  selectedLessonId: string | null;
  checked: Set<string>;
  onCheckedChange: (next: Set<string>) => void;
  onOpenLesson: (lessonId: string) => void;
  onOpenPage: (lessonId: string, page: number) => void;
}) {
  const generate = useGenerateLessons(lectureId);
  const lessons = outline.chapters.flatMap((c) => c.lessons);
  const selectable = lessons.filter((l) => SELECTABLE.has(l.status));
  const done = lessons.filter((l) => l.status === "completed").length;

  function toggle(ids: string[], on: boolean) {
    const next = new Set(checked);
    for (const id of ids) {
      if (on) next.add(id);
      else next.delete(id);
    }
    onCheckedChange(next);
  }

  async function submit() {
    const ids = [...checked];
    try {
      await generate.mutateAsync(ids);
      onCheckedChange(new Set());
      toast.success(`Đang tạo học liệu cho ${ids.length} bài.`);
      if (!selectedLessonId && ids[0]) onOpenLesson(ids[0]);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <div className="flex max-h-[70vh] flex-col rounded-xl border bg-card lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)]">
      <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">Mục lục</h2>
          <p className="text-xs text-muted-foreground">
            {done}/{lessons.length} bài đã tạo học liệu
          </p>
        </div>
        {selectable.length > 0 && (
          <Button
            variant="ghost"
            size="xs"
            onClick={() =>
              toggle(
                selectable.map((l) => l.id),
                checked.size < selectable.length,
              )
            }
          >
            {checked.size < selectable.length ? "Chọn tất cả" : "Bỏ chọn"}
          </Button>
        )}
      </div>

      <ol className="min-h-0 flex-1 space-y-4 overflow-y-auto px-2 py-3">
        {outline.chapters.map((chapter) => {
          const chapterSelectable = chapter.lessons.filter((l) => SELECTABLE.has(l.status));
          const allChecked =
            chapterSelectable.length > 0 && chapterSelectable.every((l) => checked.has(l.id));
          return (
            <li key={chapter.id}>
              <div className="flex items-start gap-2 px-2">
                {chapterSelectable.length > 0 ? (
                  <Checkbox
                    className="mt-0.5"
                    checked={allChecked}
                    onCheckedChange={(on) =>
                      toggle(
                        chapterSelectable.map((l) => l.id),
                        on,
                      )
                    }
                    aria-label={`Chọn cả ${chapter.title}`}
                  />
                ) : (
                  <span className="size-4 shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-snug">{chapter.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {pagesLabel(chapter.page_start, chapter.page_end)}
                  </p>
                </div>
              </div>
              <ol className="mt-1.5 space-y-0.5">
                {chapter.lessons.map((lesson) => {
                  const active = lesson.id === selectedLessonId;
                  return (
                    <li key={lesson.id}>
                      <div
                        className={cn(
                          "flex items-start gap-2 rounded-lg px-2 py-1.5",
                          active ? "bg-primary/10" : "hover:bg-muted",
                        )}
                      >
                        {SELECTABLE.has(lesson.status) ? (
                          <Checkbox
                            className="mt-0.5"
                            checked={checked.has(lesson.id)}
                            onCheckedChange={(on) => toggle([lesson.id], on)}
                            aria-label={`Chọn bài ${lesson.number}`}
                          />
                        ) : (
                          <span className="mt-0.5">
                            <StatusIcon lesson={lesson} />
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => onOpenLesson(lesson.id)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <span className="flex items-baseline justify-between gap-2">
                            <span className="text-sm leading-snug">
                              <span className="mr-1 text-muted-foreground">{lesson.number}</span>
                              {lesson.title}
                            </span>
                            <span className="shrink-0 text-xs whitespace-nowrap text-muted-foreground">
                              {pagesLabel(lesson.page_start, lesson.page_end)}
                            </span>
                          </span>
                          {(lesson.status === "queued" || lesson.status === "processing") && (
                            <span className="text-xs text-primary">
                              {lessonStepLabel(lesson.status, lesson.progress_step)}
                            </span>
                          )}
                          {lesson.status === "failed" && (
                            <span className="text-xs text-destructive">
                              {lesson.error?.message ?? "Lỗi"} – chọn lại để tạo lại
                            </span>
                          )}
                        </button>
                      </div>
                      {lesson.sections.length > 0 && (
                        <ul className="mb-1 ml-8 border-l pl-3">
                          {lesson.sections.map((s, i) => (
                            <li key={i}>
                              <button
                                type="button"
                                onClick={() => onOpenPage(lesson.id, s.page_start)}
                                className="flex w-full items-baseline justify-between gap-2 rounded px-1 py-0.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                              >
                                <span>{s.title}</span>
                                <span className="shrink-0 whitespace-nowrap">
                                  {pagesLabel(s.page_start, s.page_end)}
                                </span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ol>
            </li>
          );
        })}
      </ol>

      <div className="border-t p-3">
        <Button
          className="w-full"
          disabled={checked.size === 0 || generate.isPending}
          onClick={submit}
        >
          {generate.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
          {checked.size > 0
            ? `Tạo học liệu cho ${checked.size} bài đã chọn`
            : "Chọn bài để tạo học liệu"}
        </Button>
      </div>
    </div>
  );
}

"use client";

import { ArrowLeft, CheckCircle2, CircleSlash, RotateCcw, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AiNotice } from "@/components/ai-notice";
import { InlineMath } from "@/components/markdown";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useAttempt, type AttemptResult } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const LETTERS = ["A", "B", "C", "D"];

function ResultItem({
  result,
  lectureId,
  lessonId,
}: {
  result: AttemptResult["results"][number];
  lectureId: string;
  lessonId: string | null | undefined;
}) {
  const skipped = result.selected_index === null || result.selected_index === undefined;
  return (
    <li className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex items-start gap-2">
        {result.is_correct ? (
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-green-600" />
        ) : skipped ? (
          <CircleSlash className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
        ) : (
          <XCircle className="mt-0.5 size-5 shrink-0 text-destructive" />
        )}
        <p className="font-medium">
          {result.position}. <InlineMath>{result.question}</InlineMath>
        </p>
      </div>
      <ul className="grid gap-1.5 text-sm">
        {result.options.map((option, i) => {
          const correct = i === result.correct_index;
          const chosen = i === result.selected_index;
          return (
            <li
              key={i}
              className={cn(
                "flex gap-2 rounded-md border px-3 py-2",
                correct && "border-green-600/50 bg-green-600/10",
                chosen && !correct && "border-destructive/50 bg-destructive/10",
              )}
            >
              <span className="font-medium">{LETTERS[i]}.</span>
              <span className="flex-1">
                <InlineMath>{option}</InlineMath>
              </span>
              {chosen && <span className="text-xs text-muted-foreground">Bạn chọn</span>}
            </li>
          );
        })}
      </ul>
      {skipped && <p className="text-sm text-muted-foreground">Bạn bỏ trống câu này.</p>}
      <div className="rounded-md bg-muted/60 p-3 text-sm">
        <span className="font-medium">Giải thích: </span>
        <InlineMath>{result.explanation}</InlineMath>{" "}
        <Link
          href={`/lectures/${lectureId}?${lessonId ? `lesson=${lessonId}&` : ""}tab=pdf&page=${result.page_ref}`}
          className="whitespace-nowrap text-primary hover:underline"
        >
          (trang {result.page_ref})
        </Link>
      </div>
    </li>
  );
}

export default function AttemptPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isPending, error } = useAttempt(id);
  const [onlyWrong, setOnlyWrong] = useState(true);

  if (isPending) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <Alert variant="destructive" className="mx-auto max-w-3xl">
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  const percent = Math.round((data.score / data.total) * 100);
  const wrong = data.results.filter((r) => !r.is_correct);
  const shown = onlyWrong ? wrong : data.results;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        href={
          data.lesson_id
            ? `/lectures/${data.lecture_id}?lesson=${data.lesson_id}&tab=quiz`
            : `/lectures/${data.lecture_id}?tab=scope`
        }
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {data.lecture_title}
      </Link>

      <div className="grid gap-4 rounded-xl border bg-card p-5 sm:grid-cols-[auto_1fr]">
        <div className="text-center sm:pr-6">
          <p className="text-4xl font-semibold">
            {data.score}/{data.total}
          </p>
          <p className="text-sm text-muted-foreground">
            {percent}% · {formatDate(data.created_at)}
          </p>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium">{data.scope_title}</p>
          {data.by_chapter.map((ch) => (
            <div key={ch.chapter_idx} className="space-y-1">
              <div className="flex justify-between gap-2 text-xs">
                <span className="truncate">{ch.title}</span>
                <span className="shrink-0 text-muted-foreground">
                  {ch.correct}/{ch.total}
                </span>
              </div>
              <Progress value={(ch.correct / ch.total) * 100} />
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant={onlyWrong ? "default" : "outline"}
          size="sm"
          onClick={() => setOnlyWrong(true)}
        >
          Câu sai ({wrong.length})
        </Button>
        <Button
          variant={onlyWrong ? "outline" : "default"}
          size="sm"
          onClick={() => setOnlyWrong(false)}
        >
          Tất cả ({data.results.length})
        </Button>
        <Link
          href={`/quizzes/${data.quiz_id}`}
          className={buttonVariants({ variant: "outline", size: "sm", className: "ml-auto" })}
        >
          <RotateCcw /> Làm lại
        </Link>
      </div>

      <AiNotice />

      {shown.length === 0 ? (
        <p className="rounded-xl border p-6 text-center text-sm">
          Chính xác tất cả các câu. Xuất sắc!
        </p>
      ) : (
        <ol className="space-y-3">
          {shown.map((r) => (
            <ResultItem
              key={r.question_id}
              result={r}
              lectureId={data.lecture_id}
              lessonId={data.lesson_id}
            />
          ))}
        </ol>
      )}
    </div>
  );
}

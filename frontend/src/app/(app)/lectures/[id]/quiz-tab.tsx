"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { History, ListChecks, Loader2, Play, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AiNotice } from "@/components/ai-notice";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  keys,
  useAttempts,
  useLectureQuizzes,
  useLessonQuizzes,
  type LessonItem,
  type QuizSummary,
} from "@/hooks/queries";
import { api, errorMessage } from "@/lib/api";
import { formatDate, isActive } from "@/lib/format";

function AttemptHistory({ quizId }: { quizId: string }) {
  const { data, isPending } = useAttempts(quizId);
  if (isPending) return <Skeleton className="h-16 w-full" />;
  if (!data || data.items.length === 0) {
    return <p className="text-sm text-muted-foreground">Chưa có lần làm bài nào.</p>;
  }
  return (
    <ul className="divide-y text-sm">
      {data.items.map((a) => (
        <li key={a.id} className="flex items-center justify-between gap-3 py-2">
          <span className="text-muted-foreground">{formatDate(a.created_at)}</span>
          <span className="font-medium">
            {a.score}/{a.total}
          </span>
          <Link href={`/attempts/${a.id}`} className="text-primary hover:underline">
            Xem lại
          </Link>
        </li>
      ))}
    </ul>
  );
}

function QuizCard({
  quiz,
  label,
  onDelete,
}: {
  quiz: QuizSummary;
  label: string;
  onDelete: () => void;
}) {
  const [showHistory, setShowHistory] = useState(false);
  return (
    <div className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="rounded-lg bg-primary/10 p-2 text-primary">
          <ListChecks className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{label}</h3>
            {quiz.is_default && <Badge variant="secondary">Mặc định</Badge>}
            {isActive(quiz.status) && (
              <Badge variant="outline">
                <Loader2 className="animate-spin" /> Đang tạo
              </Badge>
            )}
            {quiz.status === "failed" && <Badge variant="destructive">Lỗi</Badge>}
          </div>
          <p className="text-xs text-muted-foreground">
            {quiz.num_questions} câu · tạo lúc {formatDate(quiz.created_at)}
            {quiz.attempt_count > 0 &&
              ` · ${quiz.attempt_count} lần làm · cao nhất ${quiz.best_score}/${quiz.num_questions}`}
          </p>
          {quiz.status === "failed" && (
            <p className="mt-1 text-sm text-destructive">{quiz.error?.message}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {quiz.status === "completed" && (
            <>
              <Button variant="ghost" size="sm" onClick={() => setShowHistory((v) => !v)}>
                <History /> Lịch sử
              </Button>
              <Link href={`/quizzes/${quiz.id}`} className={buttonVariants({ size: "sm" })}>
                <Play /> Làm bài
              </Link>
            </>
          )}
          {!quiz.is_default && !isActive(quiz.status) && (
            <Button variant="ghost" size="icon-sm" onClick={onDelete} aria-label="Xoá quiz">
              <Trash2 />
            </Button>
          )}
        </div>
      </div>
      {showHistory && <AttemptHistory quizId={quiz.id} />}
    </div>
  );
}

function QuizCards({
  items,
  label,
  onChanged,
}: {
  items: QuizSummary[];
  label: (q: QuizSummary) => string;
  onChanged: () => void;
}) {
  const [deleting, setDeleting] = useState<QuizSummary | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => api<void>(`/quizzes/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      onChanged();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <>
      <div className="space-y-3">
        {items.map((quiz) => (
          <QuizCard
            key={quiz.id}
            quiz={quiz}
            label={label(quiz)}
            onDelete={() => setDeleting(quiz)}
          />
        ))}
      </div>
      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xoá quiz?</AlertDialogTitle>
            <AlertDialogDescription>
              Câu hỏi và lịch sử làm bài của quiz này sẽ bị xoá.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Huỷ</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => deleting && remove.mutate(deleting.id)}
            >
              Xoá
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

const LESSON_SIZES = [5, 10, 15, 20] as const;

/** Quiz của một bài: quiz mặc định (phủ các mục) + tạo thêm. */
export function QuizTab({ lessonId }: { lessonId: string }) {
  const qc = useQueryClient();
  const { data, isPending, error } = useLessonQuizzes(lessonId, true);
  const refresh = () => void qc.invalidateQueries({ queryKey: keys.lessonQuizzes(lessonId) });

  const create = useMutation({
    mutationFn: (num: number) =>
      api<QuizSummary>(`/lessons/${lessonId}/quizzes`, {
        method: "POST",
        json: { num_questions: num },
      }),
    onSuccess: () => {
      toast.success("Đang tạo quiz mới, vui lòng chờ trong giây lát.");
      refresh();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isPending) return <Skeleton className="h-24 w-full" />;
  if (error) return <p className="text-destructive">{errorMessage(error)}</p>;

  return (
    <div className="space-y-4">
      <AiNotice />
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-sm text-muted-foreground">Tạo thêm quiz cho bài này:</span>
        {LESSON_SIZES.map((n) => (
          <Button
            key={n}
            variant="outline"
            size="sm"
            disabled={create.isPending}
            onClick={() => create.mutate(n)}
          >
            <Plus /> {n} câu
          </Button>
        ))}
      </div>
      {data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Chưa có quiz nào.</p>
      ) : (
        <QuizCards
          items={data.items}
          label={(q) => (q.is_default ? "Quiz ôn tập của bài" : "Quiz thêm")}
          onChanged={refresh}
        />
      )}
    </div>
  );
}

const SCOPE_SIZES = [10, 20, 30] as const;

/** Quiz tổng hợp: người dùng chọn phạm vi là các bài đã tạo học liệu (ADR-0017). */
export function ScopeQuizTab({ lectureId, lessons }: { lectureId: string; lessons: LessonItem[] }) {
  const qc = useQueryClient();
  const { data, isPending, error } = useLectureQuizzes(lectureId, true);
  const ready = lessons.filter((l) => l.status === "completed");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [size, setSize] = useState<number>(20);
  const refresh = () => void qc.invalidateQueries({ queryKey: keys.lectureQuizzes(lectureId) });

  const create = useMutation({
    mutationFn: () =>
      api<QuizSummary>(`/lectures/${lectureId}/quizzes`, {
        method: "POST",
        json: {
          num_questions: size,
          lesson_ids: ready.filter((l) => picked.has(l.id)).map((l) => l.id),
        },
      }),
    onSuccess: () => {
      toast.success("Đang tạo quiz tổng hợp, vui lòng chờ trong giây lát.");
      setPicked(new Set());
      refresh();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const byId = new Map(lessons.map((l) => [l.id, l]));
  const scopeQuizzes = (data?.items ?? []).filter((q) => q.lesson_id === null);

  return (
    <div className="space-y-5">
      <div className="space-y-3 rounded-xl border p-4">
        <div>
          <h3 className="font-medium">Tạo quiz tổng hợp</h3>
          <p className="text-sm text-muted-foreground">
            Chọn các bài làm phạm vi ôn tập; câu hỏi được phân bổ theo độ dài từng bài.
          </p>
        </div>
        {ready.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Chưa có bài nào được tạo học liệu. Hãy chọn bài trong mục lục trước.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {ready.map((l) => (
                <label key={l.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={picked.has(l.id)}
                    onCheckedChange={(on) => {
                      const next = new Set(picked);
                      if (on) next.add(l.id);
                      else next.delete(l.id);
                      setPicked(next);
                    }}
                  />
                  <span>
                    <span className="text-muted-foreground">{l.number}</span> {l.title}
                  </span>
                </label>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Số câu:</span>
              {SCOPE_SIZES.map((n) => (
                <Button
                  key={n}
                  size="sm"
                  variant={size === n ? "default" : "outline"}
                  onClick={() => setSize(n)}
                >
                  {n}
                </Button>
              ))}
              <Button
                size="sm"
                className="ml-auto"
                disabled={picked.size === 0 || create.isPending}
                onClick={() => create.mutate()}
              >
                {create.isPending ? <Loader2 className="animate-spin" /> : <Plus />}
                Tạo quiz {picked.size > 0 ? `(${picked.size} bài)` : ""}
              </Button>
            </div>
          </>
        )}
      </div>

      {isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : error ? (
        <p className="text-destructive">{errorMessage(error)}</p>
      ) : scopeQuizzes.length > 0 ? (
        <QuizCards
          items={scopeQuizzes}
          label={(q) => {
            const names = (q.lesson_ids ?? []).map((id) => byId.get(id)?.number).filter(Boolean);
            return `Quiz tổng hợp: bài ${names.join(", ")}`;
          }}
          onChanged={refresh}
        />
      ) : null}
    </div>
  );
}

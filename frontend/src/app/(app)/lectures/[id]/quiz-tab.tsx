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
import { Skeleton } from "@/components/ui/skeleton";
import { keys, useAttempts, useQuizzes, type QuizSummary } from "@/hooks/queries";
import { api, errorMessage } from "@/lib/api";
import { formatDate, isActive } from "@/lib/format";

const SIZES = [10, 20, 30] as const;

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

function QuizCard({ quiz, onDelete }: { quiz: QuizSummary; onDelete: () => void }) {
  const [showHistory, setShowHistory] = useState(false);
  return (
    <div className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="rounded-lg bg-primary/10 p-2 text-primary">
          <ListChecks className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">Quiz {quiz.num_questions} câu</h3>
            {quiz.is_default && <Badge variant="secondary">Mặc định</Badge>}
            {isActive(quiz.status) && (
              <Badge variant="outline">
                <Loader2 className="animate-spin" /> Đang tạo
              </Badge>
            )}
            {quiz.status === "failed" && <Badge variant="destructive">Lỗi</Badge>}
          </div>
          <p className="text-xs text-muted-foreground">
            Tạo lúc {formatDate(quiz.created_at)}
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

export function QuizTab({ lectureId }: { lectureId: string }) {
  const qc = useQueryClient();
  const { data, isPending, error } = useQuizzes(lectureId, true);
  const [deleting, setDeleting] = useState<QuizSummary | null>(null);

  const create = useMutation({
    mutationFn: (num: number) =>
      api<QuizSummary>(`/lectures/${lectureId}/quizzes`, {
        method: "POST",
        json: { num_questions: num },
      }),
    onSuccess: () => {
      toast.success("Đang tạo quiz mới, vui lòng chờ trong giây lát.");
      void qc.invalidateQueries({ queryKey: keys.quizzes(lectureId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api<void>(`/quizzes/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: keys.quizzes(lectureId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isPending) return <Skeleton className="h-24 w-full" />;
  if (error) return <p className="text-destructive">{errorMessage(error)}</p>;

  return (
    <div className="space-y-4">
      <AiNotice />
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-sm text-muted-foreground">Tạo quiz mới:</span>
        {SIZES.map((n) => (
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
        <div className="space-y-3">
          {data.items.map((quiz) => (
            <QuizCard key={quiz.id} quiz={quiz} onDelete={() => setDeleting(quiz)} />
          ))}
        </div>
      )}

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
    </div>
  );
}

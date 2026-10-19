"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, Loader2, Send } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { InlineMath } from "@/components/markdown";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { Button, buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { keys, useQuiz, type AttemptResult } from "@/hooks/queries";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

const LETTERS = ["A", "B", "C", "D"];

export default function QuizPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: quiz, isPending, error } = useQuiz(id);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [confirming, setConfirming] = useState(false);

  const submit = useMutation({
    mutationFn: () =>
      api<AttemptResult>(`/quizzes/${id}/attempts`, { method: "POST", json: { answers } }),
    onSuccess: (result) => {
      qc.setQueryData(keys.attempt(result.id), result);
      void qc.invalidateQueries({ queryKey: keys.attempts(id) });
      void qc.invalidateQueries({ queryKey: keys.lectureQuizzes(result.lecture_id) });
      if (result.lesson_id) {
        void qc.invalidateQueries({ queryKey: keys.lessonQuizzes(result.lesson_id) });
      }
      router.push(`/attempts/${result.id}`);
    },
  });

  if (isPending) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !quiz) {
    return (
      <Alert variant="destructive" className="mx-auto max-w-2xl">
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  const questions = quiz.questions;
  const lectureLink = quiz.lesson_id
    ? `/lectures/${quiz.lecture_id}?lesson=${quiz.lesson_id}&tab=quiz`
    : `/lectures/${quiz.lecture_id}?tab=scope`;
  const question = questions[index];
  const answered = Object.keys(answers).length;
  const unanswered = questions.length - answered;

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="space-y-2">
        <Link
          href={lectureLink}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> {quiz.lecture_title}
        </Link>
        <h1 className="text-lg font-semibold">{quiz.scope_title}</h1>
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">
            Câu {index + 1}/{questions.length}
          </span>
          <span className="text-muted-foreground">Đã trả lời {answered}</span>
        </div>
        <Progress value={(answered / questions.length) * 100} />
      </div>

      <div className="space-y-4 rounded-xl border bg-card p-5">
        <h1 className="text-lg font-medium leading-relaxed">
          <InlineMath>{question.question}</InlineMath>
        </h1>
        <div className="grid gap-2" role="radiogroup">
          {question.options.map((option, i) => {
            const selected = answers[question.id] === i;
            return (
              <button
                key={i}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setAnswers((a) => ({ ...a, [question.id]: i }))}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3 text-left text-sm transition-colors hover:bg-muted",
                  selected && "border-primary bg-primary/5 hover:bg-primary/10",
                )}
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                    selected && "border-primary bg-primary text-primary-foreground",
                  )}
                >
                  {LETTERS[i]}
                </span>
                <span className="pt-0.5">
                  <InlineMath>{option}</InlineMath>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={() => setIndex((i) => i - 1)} disabled={index === 0}>
          <ChevronLeft /> Câu trước
        </Button>
        {index < questions.length - 1 ? (
          <Button variant="outline" onClick={() => setIndex((i) => i + 1)}>
            Câu sau <ChevronRight />
          </Button>
        ) : null}
        <Button
          className="ml-auto"
          onClick={() => (unanswered > 0 ? setConfirming(true) : submit.mutate())}
          disabled={submit.isPending}
        >
          {submit.isPending ? <Loader2 className="animate-spin" /> : <Send />} Nộp bài
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {questions.map((q, i) => (
          <button
            key={q.id}
            type="button"
            onClick={() => setIndex(i)}
            aria-label={`Câu ${i + 1}`}
            className={cn(
              "size-8 rounded-md border text-xs",
              answers[q.id] !== undefined && "border-primary bg-primary/10",
              i === index && "ring-2 ring-primary",
            )}
          >
            {i + 1}
          </button>
        ))}
      </div>

      {submit.error && (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage(submit.error)}</AlertDescription>
        </Alert>
      )}

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Nộp bài?</AlertDialogTitle>
            <AlertDialogDescription>
              Bạn còn {unanswered} câu chưa trả lời. Câu bỏ trống được tính là sai.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Làm tiếp</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirming(false);
                submit.mutate();
              }}
            >
              Nộp bài
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Link href={lectureLink} className={buttonVariants({ variant: "link", className: "px-0" })}>
        Thoát, không lưu
      </Link>
    </div>
  );
}

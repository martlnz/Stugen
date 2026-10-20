"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowLeft, ArrowUp, Loader2, Plus, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { keys, useQuizEdit, type QuestionInput, type QuizEditable } from "@/hooks/queries";
import { api, ApiError, errorMessage } from "@/lib/api";
import { pagesLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

const LETTERS = ["A", "B", "C", "D"];
const MAX_QUESTIONS = 30;

type Lesson = QuizEditable["lessons"][number];

type Draft = {
  key: string;
  id: string | null;
  question: string;
  options: string[];
  answerIndex: number;
  explanation: string;
  page: string;
  lessonId: string;
  source: QuizEditable["questions"][number]["source"];
};

type DraftErrors = Partial<Record<"question" | "options" | "page" | "lesson", string>>;

function fromQuiz(quiz: QuizEditable): Draft[] {
  return quiz.questions.map((q) => ({
    key: q.id,
    id: q.id,
    question: q.question,
    options: [...q.options],
    answerIndex: q.answer_index,
    explanation: q.explanation,
    page: q.page_ref === null ? "" : String(q.page_ref),
    lessonId: q.lesson_id ?? quiz.lessons[0].id,
    source: q.source,
  }));
}

function toInput(d: Draft): QuestionInput {
  return {
    id: d.id,
    question: d.question.trim(),
    options: d.options.map((o) => o.trim()),
    answer_index: d.answerIndex,
    explanation: d.explanation.trim(),
    page_ref: d.page.trim() === "" ? null : Number(d.page),
    lesson_id: d.lessonId,
  };
}

/** Kiểm tra phía client, khớp ràng buộc của `PUT /quizzes/{id}/questions`. */
function validate(d: Draft, lesson: Lesson | undefined): DraftErrors {
  const errors: DraftErrors = {};
  const question = d.question.trim();
  if (!question) errors.question = "Nhập nội dung câu hỏi.";
  else if (question.length > 1000) errors.question = "Tối đa 1000 ký tự.";
  const options = d.options.map((o) => o.trim());
  if (options.some((o) => !o)) errors.options = "Nhập đủ 4 lựa chọn.";
  else if (options.some((o) => o.length > 300)) errors.options = "Mỗi lựa chọn tối đa 300 ký tự.";
  else if (new Set(options.map((o) => o.toLowerCase())).size !== 4) {
    errors.options = "Các lựa chọn không được trùng nhau.";
  }
  if (!lesson) errors.lesson = "Chọn bài.";
  const page = d.page.trim();
  if (page && lesson) {
    const n = Number(page);
    if (!Number.isInteger(n) || n < lesson.page_start || n > lesson.page_end) {
      errors.page = `Trang phải nằm trong khoảng ${lesson.page_start}–${lesson.page_end}.`;
    }
  }
  return errors;
}

const SERVER_FIELDS: Record<string, keyof DraftErrors> = {
  question: "question",
  options: "options",
  page_ref: "page",
  lesson_id: "lesson",
};

/** `questions.<i>.<trường>` → lỗi theo câu (theo `key` của bản nháp). */
function serverErrors(err: unknown, drafts: Draft[]): Record<string, DraftErrors> {
  const out: Record<string, DraftErrors> = {};
  if (!(err instanceof ApiError)) return out;
  for (const e of err.errors) {
    const [root, index, field] = e.field.split(".");
    const draft = root === "questions" ? drafts[Number(index)] : undefined;
    const target = field ? SERVER_FIELDS[field] : undefined;
    if (draft && target) out[draft.key] = { ...out[draft.key], [target]: e.message };
  }
  return out;
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-xs text-destructive">{message}</p>;
}

function QuestionCard({
  draft,
  index,
  total,
  lessons,
  scoped,
  errors,
  onChange,
  onMove,
  onRemove,
}: {
  draft: Draft;
  index: number;
  total: number;
  lessons: Lesson[];
  scoped: boolean;
  errors: DraftErrors;
  onChange: (patch: Partial<Draft>) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
}) {
  const lesson = lessons.find((l) => l.id === draft.lessonId);
  const id = `q-${draft.key}`;
  return (
    <li className="space-y-4 rounded-xl border bg-card p-4">
      <div className="flex items-center gap-2">
        <span className="font-medium">Câu {index + 1}</span>
        {draft.id === null && <Badge variant="secondary">Nhập tay</Badge>}
        {draft.source === "edited" && <Badge variant="outline">Đã sửa</Badge>}
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onMove(-1)}
            disabled={index === 0}
            aria-label="Chuyển lên"
          >
            <ArrowUp />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onMove(1)}
            disabled={index === total - 1}
            aria-label="Chuyển xuống"
          >
            <ArrowDown />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onRemove}
            disabled={total === 1}
            aria-label="Xoá câu hỏi"
          >
            <Trash2 />
          </Button>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${id}-question`}>Câu hỏi</Label>
        <Textarea
          id={`${id}-question`}
          value={draft.question}
          onChange={(e) => onChange({ question: e.target.value })}
          aria-invalid={Boolean(errors.question)}
        />
        <FieldError message={errors.question} />
      </div>

      <div className="space-y-1.5">
        <p className="text-sm font-medium">Lựa chọn · chọn đáp án đúng</p>
        <RadioGroup
          value={String(draft.answerIndex)}
          onValueChange={(v) => onChange({ answerIndex: Number(v) })}
          aria-label="Đáp án đúng"
        >
          {draft.options.map((option, i) => (
            <div
              key={i}
              className={cn(
                "flex items-center gap-3 rounded-lg border p-2",
                draft.answerIndex === i && "border-primary bg-primary/5",
              )}
            >
              <RadioGroupItem value={String(i)} aria-label={`Đáp án ${LETTERS[i]}`} />
              <span className="w-4 text-sm font-medium">{LETTERS[i]}</span>
              <Textarea
                rows={1}
                className="min-h-8 py-1"
                value={option}
                onChange={(e) =>
                  onChange({
                    options: draft.options.map((o, j) => (j === i ? e.target.value : o)),
                  })
                }
                aria-label={`Lựa chọn ${LETTERS[i]}`}
                aria-invalid={Boolean(errors.options)}
              />
            </div>
          ))}
        </RadioGroup>
        <FieldError message={errors.options} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${id}-explanation`}>Giải thích (không bắt buộc)</Label>
        <Textarea
          id={`${id}-explanation`}
          value={draft.explanation}
          onChange={(e) => onChange({ explanation: e.target.value })}
        />
      </div>

      <div className="flex flex-wrap gap-4">
        {scoped && (
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label htmlFor={`${id}-lesson`}>Bài</Label>
            <select
              id={`${id}-lesson`}
              value={draft.lessonId}
              onChange={(e) => onChange({ lessonId: e.target.value })}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm dark:bg-input/30"
            >
              {lessons.map((l) => (
                <option key={l.id} value={l.id}>
                  Bài {l.number}: {l.title}
                </option>
              ))}
            </select>
            <FieldError message={errors.lesson} />
          </div>
        )}
        <div className="w-40 space-y-1.5">
          <Label htmlFor={`${id}-page`}>Trang (không bắt buộc)</Label>
          <Input
            id={`${id}-page`}
            type="number"
            inputMode="numeric"
            value={draft.page}
            placeholder={lesson ? pagesLabel(lesson.page_start, lesson.page_end) : ""}
            onChange={(e) => onChange({ page: e.target.value })}
            aria-invalid={Boolean(errors.page)}
          />
          <FieldError message={errors.page} />
        </div>
      </div>
    </li>
  );
}

function QuizEditor({ quiz }: { quiz: QuizEditable }) {
  const router = useRouter();
  const qc = useQueryClient();
  const initial = useMemo(() => fromQuiz(quiz), [quiz]);
  const [drafts, setDrafts] = useState<Draft[]>(initial);
  const [showErrors, setShowErrors] = useState(false);
  const [confirmSave, setConfirmSave] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);

  const scoped = quiz.lesson_id === null;
  const backLink = quiz.lesson_id
    ? `/lectures/${quiz.lecture_id}?lesson=${quiz.lesson_id}&tab=quiz`
    : `/lectures/${quiz.lecture_id}?tab=scope`;
  const dirty = JSON.stringify(drafts.map(toInput)) !== JSON.stringify(initial.map(toInput));

  const save = useMutation({
    mutationFn: () =>
      api<QuizEditable>(`/quizzes/${quiz.id}/questions`, {
        method: "PUT",
        json: { questions: drafts.map(toInput) },
      }),
    onSuccess: (result) => {
      qc.setQueryData(keys.quizEdit(quiz.id), result);
      void qc.invalidateQueries({ queryKey: keys.quiz(quiz.id), exact: true });
      void qc.invalidateQueries({ queryKey: keys.attempts(quiz.id) });
      void qc.invalidateQueries({ queryKey: keys.lectureQuizzes(quiz.lecture_id) });
      if (quiz.lesson_id) {
        void qc.invalidateQueries({ queryKey: keys.lessonQuizzes(quiz.lesson_id) });
      }
      toast.success("Đã lưu quiz.");
      router.push(backLink);
    },
  });

  useEffect(() => {
    if (!dirty || save.isSuccess) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, save.isSuccess]);

  const lessonOf = (d: Draft) => quiz.lessons.find((l) => l.id === d.lessonId);
  const clientErrors = Object.fromEntries(drafts.map((d) => [d.key, validate(d, lessonOf(d))]));
  const errorCount = drafts.filter((d) => Object.keys(clientErrors[d.key]).length > 0).length;
  const fromServer = serverErrors(save.error, drafts);

  const update = (key: string, patch: Partial<Draft>) => {
    save.reset();
    setDrafts((ds) => ds.map((d) => (d.key === key ? { ...d, ...patch } : d)));
  };
  const move = (index: number, delta: number) => {
    setDrafts((ds) => {
      const next = [...ds];
      const [item] = next.splice(index, 1);
      next.splice(index + delta, 0, item);
      return next;
    });
  };
  const add = () => {
    setDrafts((ds) => [
      ...ds,
      {
        key: crypto.randomUUID(),
        id: null,
        question: "",
        options: ["", "", "", ""],
        answerIndex: 0,
        explanation: "",
        page: "",
        lessonId: ds.at(-1)?.lessonId ?? quiz.lessons[0].id,
        source: "manual",
      },
    ]);
  };
  const requestSave = () => {
    setShowErrors(true);
    if (errorCount > 0) {
      toast.error(`Còn ${errorCount} câu chưa hợp lệ.`);
      return;
    }
    if (quiz.attempt_count > 0) setConfirmSave(true);
    else save.mutate();
  };

  return (
    <div className="mx-auto max-w-2xl space-y-5 pb-24">
      <div className="space-y-2">
        <Link
          href={backLink}
          onClick={(e) => {
            if (dirty) {
              e.preventDefault();
              setConfirmLeave(true);
            }
          }}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> {quiz.lecture_title}
        </Link>
        <h1 className="text-lg font-semibold">Sửa quiz · {quiz.scope_title}</h1>
        <p className="text-sm text-muted-foreground">
          {drafts.length} câu · lựa chọn giữ đúng thứ tự bạn nhập. Tạo lại nội dung bài giảng sẽ xoá
          các chỉnh sửa này.
        </p>
      </div>

      {quiz.attempt_count > 0 && (
        <Alert>
          <AlertDescription>
            Quiz đã có {quiz.attempt_count} lần làm bài. Lưu chỉnh sửa sẽ xoá lịch sử làm bài này.
          </AlertDescription>
        </Alert>
      )}

      <ol className="space-y-4">
        {drafts.map((d, i) => (
          <QuestionCard
            key={d.key}
            draft={d}
            index={i}
            total={drafts.length}
            lessons={quiz.lessons}
            scoped={scoped}
            errors={{ ...(showErrors ? clientErrors[d.key] : {}), ...fromServer[d.key] }}
            onChange={(patch) => update(d.key, patch)}
            onMove={(delta) => move(i, delta)}
            onRemove={() => setDrafts((ds) => ds.filter((x) => x.key !== d.key))}
          />
        ))}
      </ol>

      <Button
        variant="outline"
        className="w-full"
        onClick={add}
        disabled={drafts.length >= MAX_QUESTIONS}
      >
        <Plus /> Thêm câu hỏi
        {drafts.length >= MAX_QUESTIONS && ` (tối đa ${MAX_QUESTIONS} câu)`}
      </Button>

      {save.error && (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage(save.error)}</AlertDescription>
        </Alert>
      )}

      <div className="sticky bottom-0 flex items-center gap-2 border-t bg-background/95 py-3 backdrop-blur">
        <span className="text-sm text-muted-foreground">
          {dirty ? "Có thay đổi chưa lưu" : "Chưa có thay đổi"}
        </span>
        <Button
          variant="ghost"
          className="ml-auto"
          onClick={() => (dirty ? setConfirmLeave(true) : router.push(backLink))}
        >
          Huỷ
        </Button>
        <Button onClick={requestSave} disabled={!dirty || save.isPending}>
          {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Lưu
        </Button>
      </div>

      <AlertDialog open={confirmSave} onOpenChange={setConfirmSave}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Lưu chỉnh sửa?</AlertDialogTitle>
            <AlertDialogDescription>
              {quiz.attempt_count} lần làm bài cũ của quiz này sẽ bị xoá vì câu hỏi đã thay đổi.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Quay lại</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirmSave(false);
                save.mutate();
              }}
            >
              Lưu và xoá lịch sử
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmLeave} onOpenChange={setConfirmLeave}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Bỏ các thay đổi?</AlertDialogTitle>
            <AlertDialogDescription>Các chỉnh sửa chưa lưu sẽ bị mất.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Sửa tiếp</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => router.push(backLink)}>
              Bỏ thay đổi
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function QuizEditPage() {
  const { id } = useParams<{ id: string }>();
  const { data: quiz, isPending, error } = useQuizEdit(id);

  if (isPending) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-72 w-full" />
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
  return <QuizEditor key={quiz.edited_at ?? quiz.id} quiz={quiz} />;
}

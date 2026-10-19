"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Loader2,
  MousePointerClick,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useGenerateLessons,
  useLecture,
  useOutline,
  useRegenerateLecture,
  useRetryLecture,
  type LessonItem,
} from "@/hooks/queries";
import { ApiError, errorMessage } from "@/lib/api";
import { formatBytes, formatDate, isActive, lessonStepLabel, pagesLabel } from "@/lib/format";

import { OutlinePanel } from "./outline-panel";
import { QuizTab, ScopeQuizTab } from "./quiz-tab";
import { SummaryTab } from "./summary-tab";

const SlidesTab = dynamic(() => import("./slides-tab").then((m) => m.SlidesTab), {
  ssr: false,
  loading: () => <Skeleton className="aspect-video w-full" />,
});
const PdfTab = dynamic(() => import("./pdf-tab").then((m) => m.PdfTab), {
  ssr: false,
  loading: () => <Skeleton className="h-[70vh] w-full" />,
});

type Tab = "summary" | "slides" | "quiz" | "pdf" | "scope";
const TABS: Tab[] = ["summary", "slides", "quiz", "pdf", "scope"];

function LessonStatus({ lectureId, lesson }: { lectureId: string; lesson: LessonItem }) {
  const generate = useGenerateLessons(lectureId);
  const active = lesson.status === "queued" || lesson.status === "processing";

  async function run() {
    try {
      await generate.mutateAsync([lesson.id]);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  if (lesson.status === "completed") return null;
  if (active) {
    return (
      <Alert>
        <Loader2 className="animate-spin" />
        <AlertDescription>
          {lessonStepLabel(lesson.status, lesson.progress_step)} Thường mất 30–60 giây mỗi bài; bạn
          có thể xem PDF gốc trong lúc chờ.
        </AlertDescription>
      </Alert>
    );
  }
  return (
    <Alert variant={lesson.status === "failed" ? "destructive" : "default"}>
      {lesson.status === "failed" ? <AlertTriangle /> : <Sparkles />}
      <AlertDescription>
        <p>
          {lesson.status === "failed"
            ? (lesson.error?.message ?? "Tạo học liệu thất bại.")
            : "Bài này chưa có tóm tắt, slide và quiz."}
        </p>
        <Button size="sm" className="mt-2" onClick={run} disabled={generate.isPending}>
          {generate.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
          {lesson.status === "failed" ? "Tạo lại học liệu" : "Tạo học liệu cho bài này"}
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function RegenerateBanner({ lectureId }: { lectureId: string }) {
  const regenerate = useRegenerateLecture();
  const [open, setOpen] = useState(false);
  return (
    <Alert>
      <RotateCcw />
      <AlertTitle>Bài giảng được tạo theo cách cũ</AlertTitle>
      <AlertDescription>
        <p>
          Tạo lại để tách giáo trình thành các bài nhỏ, chọn bài cần học và nhận tóm tắt theo mục,
          slide có giải thích và ví dụ, quiz riêng cho từng bài.
        </p>
        <Button size="sm" className="mt-2" onClick={() => setOpen(true)}>
          <RotateCcw /> Tạo lại nội dung
        </Button>
      </AlertDescription>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Tạo lại nội dung?</AlertDialogTitle>
            <AlertDialogDescription>
              Tóm tắt, slide, quiz và lịch sử làm bài hiện có sẽ bị xoá. File PDF được giữ nguyên.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Huỷ</AlertDialogCancel>
            <AlertDialogAction
              disabled={regenerate.isPending}
              onClick={async () => {
                try {
                  await regenerate.mutateAsync(lectureId);
                  setOpen(false);
                } catch (err) {
                  toast.error(errorMessage(err));
                }
              }}
            >
              Tạo lại
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Alert>
  );
}

function LectureView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { data: lecture, isPending, error } = useLecture(id);
  const ready = lecture?.status === "completed" && !lecture.needs_regenerate;
  const outline = useOutline(id, ready);
  const retry = useRetryLecture();
  const [checked, setChecked] = useState<Set<string>>(new Set());

  if (isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (error || !lecture) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>
            {notFound ? "Không tìm thấy bài giảng." : errorMessage(error)}
          </AlertDescription>
        </Alert>
        <Link href="/library" className={buttonVariants({ variant: "outline" })}>
          <ArrowLeft /> Về thư viện
        </Link>
      </div>
    );
  }

  const lessons = outline.data?.chapters.flatMap((c) => c.lessons) ?? [];
  const lessonId = params.get("lesson");
  const lesson = lessons.find((l) => l.id === lessonId) ?? null;
  const enabled: Record<Tab, boolean> = {
    summary: !!lesson?.available.summary,
    slides: !!lesson?.available.slides,
    quiz: !!lesson?.available.quiz,
    pdf: true,
    scope: ready,
  };
  const requested = params.get("tab") as Tab | null;
  const tab: Tab =
    requested && TABS.includes(requested) && enabled[requested]
      ? requested
      : lesson?.available.summary
        ? "summary"
        : "pdf";
  const page = Number(params.get("page")) || lesson?.page_start || 1;

  function go(next: { lesson?: string | null; tab?: Tab; page?: number }) {
    const sp = new URLSearchParams();
    const nextLesson = next.lesson === undefined ? lessonId : next.lesson;
    if (nextLesson) sp.set("lesson", nextLesson);
    if (next.tab) sp.set("tab", next.tab);
    if (next.page) sp.set("page", String(next.page));
    router.replace(`${pathname}?${sp.toString()}`, { scroll: false });
  }

  async function onRetry() {
    try {
      await retry.mutateAsync(lecture!.id);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Link
          href="/library"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Thư viện
        </Link>
        <h1 className="text-2xl leading-tight font-semibold">{lecture.title}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <StatusBadge status={lecture.status} />
          <span>{lecture.page_count} trang</span>
          <span>{formatBytes(lecture.file_size)}</span>
          <span>{formatDate(lecture.created_at)}</span>
        </div>
      </div>

      {isActive(lecture.status) && (
        <Alert>
          <Loader2 className="animate-spin" />
          <AlertDescription>
            Đang tách giáo trình thành các chương và bài nhỏ, thường chỉ mất vài giây…
          </AlertDescription>
        </Alert>
      )}

      {lecture.status === "failed" && (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Xử lý thất bại</AlertTitle>
          <AlertDescription>
            <p>{lecture.error?.message ?? "Đã xảy ra lỗi, vui lòng thử lại."}</p>
            {lecture.error?.code !== "PDF_NO_TEXT" && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={onRetry}
                disabled={retry.isPending}
              >
                {retry.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />} Thử lại
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {lecture.needs_regenerate && <RegenerateBanner lectureId={lecture.id} />}

      {ready && (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(300px,360px)_1fr]">
          {outline.data ? (
            <OutlinePanel
              lectureId={lecture.id}
              outline={outline.data}
              selectedLessonId={lesson?.id ?? null}
              checked={checked}
              onCheckedChange={setChecked}
              onOpenLesson={(lid) => go({ lesson: lid })}
              onOpenPage={(lid, p) => go({ lesson: lid, tab: "pdf", page: p })}
            />
          ) : (
            <Skeleton className="h-96 w-full" />
          )}

          <div className="min-w-0 space-y-4">
            {lesson ? (
              <div className="space-y-3">
                <div>
                  <p className="text-sm text-muted-foreground">
                    Bài {lesson.number} · {pagesLabel(lesson.page_start, lesson.page_end)}
                  </p>
                  <h2 className="text-xl font-semibold">{lesson.title}</h2>
                </div>
                <LessonStatus lectureId={lecture.id} lesson={lesson} />
              </div>
            ) : (
              <Alert>
                <MousePointerClick />
                <AlertTitle>Chọn bài để học</AlertTitle>
                <AlertDescription>
                  Giáo trình đã được tách thành {lessons.length} bài nhỏ. Tick các bài cần học trong
                  mục lục rồi bấm &ldquo;Tạo học liệu&rdquo;: mỗi bài có tóm tắt theo mục, slide có
                  giải thích và ví dụ, quiz riêng. Bấm vào tên bài để xem.
                </AlertDescription>
              </Alert>
            )}

            <Tabs value={tab} onValueChange={(v) => go({ tab: v as Tab })}>
              <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
                <TabsTrigger value="summary" disabled={!enabled.summary}>
                  Tóm tắt
                </TabsTrigger>
                <TabsTrigger value="slides" disabled={!enabled.slides}>
                  Slide
                </TabsTrigger>
                <TabsTrigger value="quiz" disabled={!enabled.quiz}>
                  Quiz
                </TabsTrigger>
                <TabsTrigger value="pdf">PDF gốc</TabsTrigger>
                <TabsTrigger value="scope">Quiz tổng hợp</TabsTrigger>
              </TabsList>
              <TabsContent value="summary" className="pt-4">
                {tab === "summary" && lesson && (
                  <SummaryTab
                    lessonId={lesson.id}
                    onOpenPage={(p) => go({ tab: "pdf", page: p })}
                  />
                )}
              </TabsContent>
              <TabsContent value="slides" className="pt-4">
                {tab === "slides" && lesson && (
                  <SlidesTab lessonId={lesson.id} title={`${lesson.number} ${lesson.title}`} />
                )}
              </TabsContent>
              <TabsContent value="quiz" className="pt-4">
                {tab === "quiz" && lesson && <QuizTab lessonId={lesson.id} />}
              </TabsContent>
              <TabsContent value="pdf" className="pt-4">
                {tab === "pdf" && <PdfTab lectureId={lecture.id} page={page} />}
              </TabsContent>
              <TabsContent value="scope" className="pt-4">
                {tab === "scope" && <ScopeQuizTab lectureId={lecture.id} lessons={lessons} />}
              </TabsContent>
            </Tabs>
          </div>
        </div>
      )}
    </div>
  );
}

export default function LecturePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <LectureView />
    </Suspense>
  );
}

"use client";

import { AlertTriangle, ArrowLeft, Loader2, RotateCcw } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { toast } from "sonner";

import { ProgressSteps } from "@/components/progress-steps";
import { StatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLecture, useRetryLecture } from "@/hooks/queries";
import { ApiError, errorMessage } from "@/lib/api";
import { formatBytes, formatDate, isActive } from "@/lib/format";

import { QuizTab } from "./quiz-tab";
import { SummaryTab } from "./summary-tab";

const SlidesTab = dynamic(() => import("./slides-tab").then((m) => m.SlidesTab), {
  ssr: false,
  loading: () => <Skeleton className="aspect-video w-full" />,
});
const PdfTab = dynamic(() => import("./pdf-tab").then((m) => m.PdfTab), {
  ssr: false,
  loading: () => <Skeleton className="h-[70vh] w-full" />,
});

type Tab = "summary" | "slides" | "quiz" | "pdf";
const TABS: Tab[] = ["summary", "slides", "quiz", "pdf"];

function LectureView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { data: lecture, isPending, error } = useLecture(id);
  const retry = useRetryLecture();

  if (isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-10 w-full" />
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

  const available = lecture.available;
  const enabled: Record<Tab, boolean> = {
    summary: available.summary,
    slides: available.slides,
    quiz: available.quiz || lecture.status === "completed",
    pdf: true,
  };
  const requested = params.get("tab") as Tab | null;
  const tab: Tab =
    requested && TABS.includes(requested) && enabled[requested]
      ? requested
      : available.summary
        ? "summary"
        : "pdf";
  const page = Number(params.get("page")) || 1;

  function go(next: Tab, nextPage?: number) {
    const sp = new URLSearchParams();
    sp.set("tab", next);
    if (nextPage) sp.set("page", String(nextPage));
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
        <h1 className="text-2xl font-semibold leading-tight">{lecture.title}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <StatusBadge status={lecture.status} />
          <span>{lecture.page_count} trang</span>
          <span>{formatBytes(lecture.file_size)}</span>
          <span>{formatDate(lecture.created_at)}</span>
        </div>
      </div>

      {isActive(lecture.status) && (
        <div className="rounded-xl border bg-card p-4">
          <p className="mb-3 text-sm text-muted-foreground">
            Đang xử lý giáo trình, thường mất 1–3 phút. Bạn có thể rời trang này, bài giảng vẫn tiếp
            tục được xử lý.
          </p>
          <ProgressSteps lecture={lecture} />
        </div>
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

      <Tabs value={tab} onValueChange={(v) => go(v as Tab)}>
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
        </TabsList>
        <TabsContent value="summary" className="pt-4">
          {tab === "summary" && (
            <SummaryTab lectureId={lecture.id} onOpenPage={(p) => go("pdf", p)} />
          )}
        </TabsContent>
        <TabsContent value="slides" className="pt-4">
          {tab === "slides" && <SlidesTab lectureId={lecture.id} title={lecture.title} />}
        </TabsContent>
        <TabsContent value="quiz" className="pt-4">
          {tab === "quiz" && <QuizTab lectureId={lecture.id} />}
        </TabsContent>
        <TabsContent value="pdf" className="pt-4">
          {tab === "pdf" && <PdfTab lectureId={lecture.id} page={page} />}
        </TabsContent>
      </Tabs>
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

import type { Schema } from "./api";

export type Lecture = Schema<"LectureOut">;
export type LectureStatus = Lecture["status"];
export type ProgressStep = NonNullable<Lecture["progress_step"]>;

export const STATUS_LABEL: Record<LectureStatus, string> = {
  queued: "Đang chờ",
  processing: "Đang xử lý",
  completed: "Hoàn tất",
  failed: "Lỗi",
};

export const STEPS: { key: ProgressStep; label: string }[] = [
  { key: "extracting", label: "Đang tách mục lục" },
  { key: "summarizing", label: "Đang tóm tắt" },
  { key: "slides", label: "Đang tạo slide" },
  { key: "quiz", label: "Đang tạo quiz" },
];

export function isActive(status: LectureStatus): boolean {
  return status === "queued" || status === "processing";
}

const dateFormat = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateFormat.format(new Date(iso)) : "";
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function pageRange(start: number, end: number): string {
  return start === end ? `trang ${start}` : `trang ${start}–${end}`;
}

export function pagesLabel(start: number, end: number): string {
  return start === end ? `tr. ${start}` : `tr. ${start}–${end}`;
}

const LESSON_STEP: Record<string, string> = {
  summarizing: "Đang tóm tắt…",
  slides: "Đang tạo slide…",
  quiz: "Đang tạo quiz…",
};

export function lessonStepLabel(status: string, step: string | null | undefined): string {
  if (status === "queued") return "Đang chờ tạo…";
  return (step && LESSON_STEP[step]) || "Đang tạo…";
}

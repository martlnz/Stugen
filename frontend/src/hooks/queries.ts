"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schema } from "@/lib/api";
import { isActive, type Lecture } from "@/lib/format";

export type LecturePage = Schema<"LecturePage">;
export type Outline = Schema<"OutlineOut">;
export type LessonItem = Schema<"LessonOut">;
export type LessonSummary = Schema<"LessonSummaryOut">;
export type LessonSlides = Schema<"LessonSlidesOut">;
export type QuizSummary = Schema<"QuizSummary">;
export type QuizDetail = Schema<"QuizDetail">;
export type AttemptResult = Schema<"AttemptResult">;
export type AttemptPage = Schema<"AttemptPage">;

export const keys = {
  lectures: ["lectures"] as const,
  lecture: (id: string) => ["lecture", id] as const,
  outline: (id: string) => ["lecture", id, "outline"] as const,
  lectureQuizzes: (id: string) => ["lecture", id, "quizzes"] as const,
  lessonSummary: (id: string) => ["lesson", id, "summary"] as const,
  lessonSlides: (id: string) => ["lesson", id, "slides"] as const,
  lessonQuizzes: (id: string) => ["lesson", id, "quizzes"] as const,
  quiz: (id: string) => ["quiz", id] as const,
  attempts: (quizId: string) => ["quiz", quizId, "attempts"] as const,
  attempt: (id: string) => ["attempt", id] as const,
};

function lessonActive(status: LessonItem["status"]): boolean {
  return status === "queued" || status === "processing";
}

/** Thư viện: polling 5 giây khi có bài giảng hoặc bài học đang xử lý (ADR-0013). */
export function useLectures() {
  return useQuery({
    queryKey: keys.lectures,
    queryFn: () => api<LecturePage>("/lectures?page_size=100"),
    refetchInterval: (query) =>
      query.state.data?.items.some((l) => isActive(l.status) || l.lessons.processing > 0)
        ? 5000
        : false,
  });
}

/** Chi tiết bài giảng: polling 3 giây khi đang tách mục lục (ADR-0013). */
export function useLecture(id: string) {
  return useQuery({
    queryKey: keys.lecture(id),
    queryFn: () => api<Lecture>(`/lectures/${id}`),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && isActive(data.status) ? 3000 : false;
    },
  });
}

/** Mục lục chương → bài; polling 3 giây khi có bài đang tạo học liệu. */
export function useOutline(lectureId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.outline(lectureId),
    queryFn: () => api<Outline>(`/lectures/${lectureId}/outline`),
    enabled,
    refetchInterval: (query) =>
      query.state.data?.chapters.some((c) => c.lessons.some((l) => lessonActive(l.status)))
        ? 3000
        : false,
  });
}

export function useLessonSummary(lessonId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.lessonSummary(lessonId),
    queryFn: () => api<LessonSummary>(`/lessons/${lessonId}/summary`),
    enabled,
    staleTime: Infinity,
  });
}

export function useLessonSlides(lessonId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.lessonSlides(lessonId),
    queryFn: () => api<LessonSlides>(`/lessons/${lessonId}/slides`),
    enabled,
    staleTime: Infinity,
  });
}

function quizPolling(data: { items: QuizSummary[] } | undefined) {
  return data?.items.some((q) => isActive(q.status)) ? 3000 : false;
}

export function useLessonQuizzes(lessonId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.lessonQuizzes(lessonId),
    queryFn: () => api<{ items: QuizSummary[] }>(`/lessons/${lessonId}/quizzes`),
    enabled,
    refetchInterval: (query) => quizPolling(query.state.data),
  });
}

export function useLectureQuizzes(lectureId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.lectureQuizzes(lectureId),
    queryFn: () => api<{ items: QuizSummary[] }>(`/lectures/${lectureId}/quizzes`),
    enabled,
    refetchInterval: (query) => quizPolling(query.state.data),
  });
}

export function useQuiz(id: string) {
  return useQuery({
    queryKey: keys.quiz(id),
    queryFn: () => api<QuizDetail>(`/quizzes/${id}`),
    staleTime: Infinity,
  });
}

export function useAttempts(quizId: string, enabled = true) {
  return useQuery({
    queryKey: keys.attempts(quizId),
    queryFn: () => api<AttemptPage>(`/quizzes/${quizId}/attempts?page_size=10`),
    enabled,
  });
}

export function useAttempt(id: string) {
  return useQuery({
    queryKey: keys.attempt(id),
    queryFn: () => api<AttemptResult>(`/attempts/${id}`),
    staleTime: Infinity,
  });
}

export function useRenameLecture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api<Lecture>(`/lectures/${id}`, { method: "PATCH", json: { title } }),
    onSuccess: (lecture) => {
      qc.setQueryData(keys.lecture(lecture.id), lecture);
      void qc.invalidateQueries({ queryKey: keys.lectures });
    },
  });
}

export function useDeleteLecture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/lectures/${id}`, { method: "DELETE" }),
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: keys.lecture(id) });
      void qc.invalidateQueries({ queryKey: keys.lectures });
    },
  });
}

export function useRetryLecture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<Lecture>(`/lectures/${id}/retry`, { method: "POST" }),
    onSuccess: (lecture) => {
      qc.setQueryData(keys.lecture(lecture.id), lecture);
      void qc.invalidateQueries({ queryKey: keys.lectures });
    },
  });
}

export function useRegenerateLecture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<Lecture>(`/lectures/${id}/regenerate`, { method: "POST" }),
    onSuccess: (lecture) => {
      qc.setQueryData(keys.lecture(lecture.id), lecture);
      qc.removeQueries({ queryKey: keys.outline(lecture.id) });
      void qc.invalidateQueries({ queryKey: keys.lectures });
    },
  });
}

export function useGenerateLessons(lectureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lessonIds: string[]) =>
      api<Outline>(`/lectures/${lectureId}/lessons/generate`, {
        method: "POST",
        json: { lesson_ids: lessonIds },
      }),
    onSuccess: (outline) => {
      qc.setQueryData(keys.outline(lectureId), outline);
      void qc.invalidateQueries({ queryKey: keys.lecture(lectureId) });
      void qc.invalidateQueries({ queryKey: keys.lectures });
    },
  });
}

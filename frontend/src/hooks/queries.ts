"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schema } from "@/lib/api";
import { isActive, type Lecture } from "@/lib/format";

export type LecturePage = Schema<"LecturePage">;
export type Summary = Schema<"SummaryOut">;
export type Slides = Schema<"SlidesOut">;
export type QuizSummary = Schema<"QuizSummary">;
export type QuizDetail = Schema<"QuizDetail">;
export type AttemptResult = Schema<"AttemptResult">;
export type AttemptPage = Schema<"AttemptPage">;

export const keys = {
  lectures: ["lectures"] as const,
  lecture: (id: string) => ["lecture", id] as const,
  summary: (id: string) => ["lecture", id, "summary"] as const,
  slides: (id: string) => ["lecture", id, "slides"] as const,
  quizzes: (id: string) => ["lecture", id, "quizzes"] as const,
  quiz: (id: string) => ["quiz", id] as const,
  attempts: (quizId: string) => ["quiz", quizId, "attempts"] as const,
  attempt: (id: string) => ["attempt", id] as const,
};

/** Thư viện: polling 5 giây chỉ khi có bài giảng đang xử lý (ADR-0013). */
export function useLectures() {
  return useQuery({
    queryKey: keys.lectures,
    queryFn: () => api<LecturePage>("/lectures?page_size=100"),
    refetchInterval: (query) =>
      query.state.data?.items.some((l) => isActive(l.status)) ? 5000 : false,
  });
}

/** Chi tiết bài giảng: polling 3 giây khi `queued`/`processing` (ADR-0013). */
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

export function useSummary(id: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.summary(id),
    queryFn: () => api<Summary>(`/lectures/${id}/summary`),
    enabled,
    staleTime: Infinity,
  });
}

export function useSlides(id: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.slides(id),
    queryFn: () => api<Slides>(`/lectures/${id}/slides`),
    enabled,
    staleTime: Infinity,
  });
}

export function useQuizzes(lectureId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.quizzes(lectureId),
    queryFn: () => api<{ items: QuizSummary[] }>(`/lectures/${lectureId}/quizzes`),
    enabled,
    refetchInterval: (query) =>
      query.state.data?.items.some((q) => isActive(q.status)) ? 3000 : false,
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

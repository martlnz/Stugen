"use client";

import { FileText, Loader2, MoreVertical, Pencil, Plus, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
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
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeleteLecture, useLectures, useRenameLecture } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";
import { formatDate, isActive, STEPS, type Lecture } from "@/lib/format";

function LectureCard({
  lecture,
  onRename,
  onDelete,
}: {
  lecture: Lecture;
  onRename: () => void;
  onDelete: () => void;
}) {
  const step = STEPS.find((s) => s.key === lecture.progress_step);
  return (
    <div className="group relative flex flex-col gap-3 rounded-xl border bg-card p-4 transition-colors hover:border-primary/40">
      <div className="flex items-start gap-3">
        <div className="rounded-lg bg-primary/10 p-2 text-primary">
          <FileText className="size-5" />
        </div>
        <Link
          href={`/lectures/${lecture.id}`}
          className="min-w-0 flex-1 after:absolute after:inset-0 after:content-['']"
        >
          <h2 className="line-clamp-2 font-medium leading-snug">{lecture.title}</h2>
        </Link>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" size="icon-sm" className="relative z-10 -mr-1" />}
            aria-label="Tuỳ chọn"
          >
            <MoreVertical />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem onClick={onRename}>
              <Pencil /> Đổi tên
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={onDelete}>
              <Trash2 /> Xoá
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <StatusBadge status={lecture.status} />
        {isActive(lecture.status) && step && (
          <span className="flex items-center gap-1">
            <Loader2 className="size-3 animate-spin" /> {step.label}
          </span>
        )}
        <span>{lecture.page_count} trang</span>
        {lecture.status === "completed" && lecture.lessons.total > 0 && (
          <span>
            {lecture.lessons.completed}/{lecture.lessons.total} bài đã tạo
            {lecture.lessons.processing > 0 && ` · ${lecture.lessons.processing} đang tạo`}
          </span>
        )}
        {lecture.needs_regenerate && <span className="text-primary">Cần tạo lại nội dung</span>}
        <span>{formatDate(lecture.created_at)}</span>
      </div>
    </div>
  );
}

function RenameDialog({ lecture, onClose }: { lecture: Lecture | null; onClose: () => void }) {
  const rename = useRenameLecture();
  const [title, setTitle] = useState("");
  const [lastId, setLastId] = useState<string | null>(null);
  if (lecture && lecture.id !== lastId) {
    setLastId(lecture.id);
    setTitle(lecture.title);
  }
  const trimmed = title.trim();
  const invalid = trimmed.length === 0 || trimmed.length > 200;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!lecture || invalid) return;
    try {
      await rename.mutateAsync({ id: lecture.id, title: trimmed });
      toast.success("Đã đổi tên bài giảng.");
      onClose();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <Dialog open={lecture !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Đổi tên bài giảng</DialogTitle>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              autoFocus
              aria-invalid={invalid}
            />
            <p className="text-xs text-muted-foreground">{trimmed.length}/200 ký tự</p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Huỷ
            </Button>
            <Button type="submit" disabled={invalid || rename.isPending}>
              {rename.isPending && <Loader2 className="animate-spin" />} Lưu
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog({ lecture, onClose }: { lecture: Lecture | null; onClose: () => void }) {
  const remove = useDeleteLecture();
  async function confirm() {
    if (!lecture) return;
    try {
      await remove.mutateAsync(lecture.id);
      toast.success("Đã xoá bài giảng.");
      onClose();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }
  return (
    <AlertDialog open={lecture !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Xoá bài giảng?</AlertDialogTitle>
          <AlertDialogDescription>
            &ldquo;{lecture?.title}&rdquo; cùng file PDF, tóm tắt, slide và quiz sẽ bị xoá vĩnh
            viễn.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Huỷ</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={confirm} disabled={remove.isPending}>
            {remove.isPending && <Loader2 className="animate-spin" />} Xoá
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default function LibraryPage() {
  const { data, isPending, isError, error, refetch } = useLectures();
  const [renaming, setRenaming] = useState<Lecture | null>(null);
  const [deleting, setDeleting] = useState<Lecture | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Thư viện</h1>
          {data && <p className="text-sm text-muted-foreground">{data.total} bài giảng</p>}
        </div>
        <Link href="/upload" className={buttonVariants()}>
          <Plus /> Tải giáo trình mới
        </Link>
      </div>

      {isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-destructive/30 p-6 text-sm">
          <p className="text-destructive">{errorMessage(error)}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={() => refetch()}>
            Thử lại
          </Button>
        </div>
      ) : data.items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-16 text-center">
          <Upload className="size-10 text-muted-foreground" />
          <h2 className="text-lg font-medium">Thư viện còn trống</h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            Tải lên giáo trình PDF đầu tiên để nhận tóm tắt, slide và quiz ôn tập.
          </p>
          <Link href="/upload" className={buttonVariants()}>
            <Plus /> Tải giáo trình
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((lecture) => (
            <LectureCard
              key={lecture.id}
              lecture={lecture}
              onRename={() => setRenaming(lecture)}
              onDelete={() => setDeleting(lecture)}
            />
          ))}
        </div>
      )}

      <RenameDialog lecture={renaming} onClose={() => setRenaming(null)} />
      <DeleteDialog lecture={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}

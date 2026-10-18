"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileText, Info, Loader2, UploadCloud, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { keys } from "@/hooks/queries";
import { api, errorMessage } from "@/lib/api";
import { formatBytes, type Lecture } from "@/lib/format";
import { cn } from "@/lib/utils";

const MAX_BYTES = 20 * 1024 * 1024;

function rejectionMessage(rejections: FileRejection[]): string {
  const code = rejections[0]?.errors[0]?.code;
  if (code === "file-too-large") return "File vượt quá 20 MB.";
  if (code === "file-invalid-type") return "Chỉ nhận file PDF.";
  if (code === "too-many-files") return "Chỉ tải lên một file mỗi lần.";
  return "File không hợp lệ.";
}

export default function UploadPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "application/pdf": [".pdf"] },
    maxSize: MAX_BYTES,
    multiple: false,
    disabled: uploading,
    onDrop: (accepted, rejected) => {
      if (rejected.length) {
        setError(rejectionMessage(rejected));
        return;
      }
      setError(null);
      setFile(accepted[0] ?? null);
    },
  });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    if (title.trim()) body.append("title", title.trim());
    try {
      const lecture = await api<Lecture>("/lectures", { method: "POST", body });
      qc.setQueryData(keys.lecture(lecture.id), lecture);
      void qc.invalidateQueries({ queryKey: keys.lectures });
      router.push(`/lectures/${lecture.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setUploading(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Tải giáo trình mới</h1>
        <p className="text-sm text-muted-foreground">
          File PDF có lớp văn bản, tối đa 20 MB và 200 trang. PDF dạng ảnh scan chưa được hỗ trợ.
        </p>
      </div>

      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
          isDragActive ? "border-primary bg-primary/5" : "hover:border-primary/50",
          uploading && "pointer-events-none opacity-60",
        )}
      >
        <input {...getInputProps()} />
        <UploadCloud className="size-10 text-muted-foreground" />
        <div>
          <p className="font-medium">
            {isDragActive ? "Thả file vào đây" : "Kéo thả file PDF vào đây"}
          </p>
          <p className="text-sm text-muted-foreground">hoặc bấm để chọn file</p>
        </div>
      </div>

      {file && (
        <div className="flex items-center gap-3 rounded-lg border p-3">
          <FileText className="size-5 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setFile(null)}
            disabled={uploading}
            aria-label="Bỏ chọn file"
          >
            <X />
          </Button>
        </div>
      )}

      <div className="grid gap-1.5">
        <Label htmlFor="title">Tên bài giảng (không bắt buộc)</Label>
        <Input
          id="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
          placeholder="Mặc định lấy từ tiêu đề PDF hoặc tên file"
          disabled={uploading}
        />
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Alert>
        <Info />
        <AlertDescription>
          Nội dung giáo trình sẽ được gửi tới dịch vụ AI bên thứ ba (mặc định DeepSeek) để tạo tóm
          tắt, slide và quiz. Không tải lên tài liệu có thông tin nhạy cảm.
        </AlertDescription>
      </Alert>

      <Button type="submit" size="lg" disabled={!file || uploading} className="w-full sm:w-auto">
        {uploading ? <Loader2 className="animate-spin" /> : <UploadCloud />}
        {uploading ? "Đang tải lên…" : "Tải lên và xử lý"}
      </Button>
    </form>
  );
}

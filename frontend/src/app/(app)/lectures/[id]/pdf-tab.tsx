"use client";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

// Worker phải khai báo trong cùng module dùng <Document>/<Page> (README react-pdf)
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfTab({ lectureId, page: initialPage }: { lectureId: string; page: number }) {
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(initialPage);
  const [lastInitial, setLastInitial] = useState(initialPage);
  const [width, setWidth] = useState(800);
  const containerRef = useRef<HTMLDivElement>(null);
  const src = `/api/lectures/${lectureId}/pdf`;

  // Trang yêu cầu từ URL thay đổi (bấm số trang ở tab khác) → nhảy tới trang đó
  if (initialPage !== lastInitial) {
    setLastInitial(initialPage);
    setPage(initialPage);
  }

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.min(entry.contentRect.width, 1000)),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const go = (p: number) => setPage(Math.min(Math.max(1, p), numPages || 1));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon-sm" onClick={() => go(page - 1)} disabled={page <= 1}>
          <ChevronLeft />
        </Button>
        <div className="flex items-center gap-1.5 text-sm">
          Trang
          <Input
            type="number"
            min={1}
            max={numPages || undefined}
            value={page}
            onChange={(e) => go(Number(e.target.value))}
            className="h-7 w-16"
            aria-label="Số trang"
          />
          / {numPages || "…"}
        </div>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => go(page + 1)}
          disabled={!numPages || page >= numPages}
        >
          <ChevronRight />
        </Button>
        <a
          href={`${src}?download=true`}
          className={buttonVariants({ variant: "outline", size: "sm", className: "ml-auto" })}
        >
          <Download /> Tải PDF
        </a>
      </div>
      <div ref={containerRef} className="flex justify-center rounded-xl border bg-muted/40 p-2">
        <Document
          file={src}
          onLoadSuccess={({ numPages: n }) => {
            setNumPages(n);
            setPage((p) => Math.min(p, n));
          }}
          loading={<Skeleton className="h-[70vh] w-full" />}
          error={<p className="p-6 text-destructive">Không tải được file PDF.</p>}
        >
          <Page
            pageNumber={page}
            width={width - 16}
            loading={<Skeleton className="h-[70vh] w-full" />}
          />
        </Document>
      </div>
    </div>
  );
}

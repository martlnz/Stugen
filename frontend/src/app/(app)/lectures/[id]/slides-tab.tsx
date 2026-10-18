"use client";

import "reveal.js/reveal.css";
import "reveal.js/theme/white.css";

import { Download, Maximize } from "lucide-react";
import { useEffect, useRef } from "react";
import Reveal from "reveal.js";

import { InlineMath } from "@/components/markdown";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSlides, type Slides } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";

type Slide = Slides["deck"]["slides"][number];

function SlideSection({ slide }: { slide: Slide }) {
  const notes = slide.notes ? <aside className="notes">{slide.notes}</aside> : null;
  if (slide.layout === "title" || slide.layout === "section") {
    return (
      <section data-background-color={slide.layout === "section" ? "#eef3fb" : undefined}>
        <h2 className="!text-[1.6em]">
          <InlineMath>{slide.title}</InlineMath>
        </h2>
        {slide.subtitle && <p className="!text-[0.7em] text-neutral-500">{slide.subtitle}</p>}
        {notes}
      </section>
    );
  }
  return (
    <section className="!text-left">
      <h3 className="!text-[1.1em]">
        <InlineMath>{slide.title}</InlineMath>
      </h3>
      <ul className="!ml-[1em] !block !text-[0.62em] !leading-snug">
        {(slide.bullets ?? []).map((b, i) => (
          <li key={i} className="!mb-[0.45em]">
            <InlineMath>{b}</InlineMath>
          </li>
        ))}
      </ul>
      {slide.page_refs && slide.page_refs.length > 0 && (
        <p className="!mt-[0.8em] !text-[0.45em] text-neutral-500">
          Trang {slide.page_refs.join(", ")}
        </p>
      )}
      {notes}
    </section>
  );
}

function Deck({ slides }: { slides: Slide[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const deck = new Reveal(ref.current, {
      embedded: true,
      hash: false,
      respondToHashChanges: false,
      history: false,
      controls: true,
      progress: true,
      slideNumber: "c/t",
      keyboardCondition: "focused",
      width: 1280,
      height: 720,
      margin: 0.06,
      transition: "slide",
    });
    void deck.initialize();
    return () => {
      try {
        deck.destroy();
      } catch {
        // Reveal đôi khi lỗi khi huỷ lúc chưa khởi tạo xong; bỏ qua
      }
    };
  }, [slides]);

  return (
    <div
      ref={ref}
      className="reveal aspect-video w-full overflow-hidden rounded-xl border"
      tabIndex={0}
    >
      <div className="slides">
        {slides.map((slide, i) => (
          <SlideSection key={i} slide={slide} />
        ))}
      </div>
    </div>
  );
}

export function SlidesTab({ lectureId, title }: { lectureId: string; title: string }) {
  const { data, isPending, error } = useSlides(lectureId, true);
  const wrapperRef = useRef<HTMLDivElement>(null);

  if (isPending) return <Skeleton className="aspect-video w-full" />;
  if (error) return <p className="text-destructive">{errorMessage(error)}</p>;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-sm text-muted-foreground">
          Bấm vào slide rồi dùng phím mũi tên để chuyển. Ghi chú thuyết trình có trong file PPTX.
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void wrapperRef.current?.requestFullscreen()}
        >
          <Maximize /> Toàn màn hình
        </Button>
        {data.pptx_available ? (
          <a
            href={`/api/lectures/${lectureId}/slides.pptx`}
            download={`${title}.pptx`}
            className={buttonVariants({ size: "sm" })}
          >
            <Download /> Tải PPTX
          </a>
        ) : (
          <Button size="sm" disabled title="Xuất PPTX thất bại">
            <Download /> PPTX không khả dụng
          </Button>
        )}
      </div>
      <div
        ref={wrapperRef}
        className="bg-white [&:fullscreen_.reveal]:h-full [&:fullscreen_.reveal]:rounded-none"
      >
        <Deck slides={data.deck.slides} />
      </div>
    </div>
  );
}

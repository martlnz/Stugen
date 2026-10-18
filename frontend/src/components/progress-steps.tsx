import { Check, Loader2 } from "lucide-react";

import { STEPS, type Lecture } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Đang trích xuất → Đang tóm tắt → Đang tạo slide → Đang tạo quiz → Hoàn tất (ADR-0013). */
export function ProgressSteps({ lecture }: { lecture: Lecture }) {
  const current = STEPS.findIndex((s) => s.key === lecture.progress_step);
  const items = [...STEPS.map((s) => s.label), "Hoàn tất"];
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm">
      {items.map((label, i) => {
        const done = lecture.status === "completed" || i < current;
        const active = lecture.status === "processing" && i === current;
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs",
                done && "border-primary bg-primary text-primary-foreground",
                active && "border-primary text-primary",
              )}
            >
              {done ? (
                <Check className="size-3.5" />
              ) : active ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                i + 1
              )}
            </span>
            <span className={cn(!done && !active && "text-muted-foreground")}>{label}</span>
            {i < items.length - 1 && <span className="hidden h-px w-6 bg-border sm:block" />}
          </li>
        );
      })}
    </ol>
  );
}

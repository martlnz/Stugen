import { Badge } from "@/components/ui/badge";
import { STATUS_LABEL, type LectureStatus } from "@/lib/format";

const VARIANT = {
  queued: "secondary",
  processing: "secondary",
  completed: "default",
  failed: "destructive",
} as const;

export function StatusBadge({ status }: { status: LectureStatus }) {
  return <Badge variant={VARIANT[status]}>{STATUS_LABEL[status]}</Badge>;
}

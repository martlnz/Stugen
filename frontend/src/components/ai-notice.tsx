import { Bot } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";

export function AiNotice() {
  return (
    <Alert>
      <Bot />
      <AlertDescription>
        Nội dung do AI tạo, có thể chưa chính xác. Hãy đối chiếu với giáo trình gốc.
      </AlertDescription>
    </Alert>
  );
}

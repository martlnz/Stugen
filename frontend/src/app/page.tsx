import { BookOpenText, FileText, ListChecks, Presentation } from "lucide-react";
import { Suspense } from "react";

import { HomeActions, LoginErrorNotice } from "./home-actions";

const FEATURES = [
  {
    icon: FileText,
    title: "Tóm tắt theo chương",
    text: "Ý chính, thuật ngữ kèm định nghĩa và số trang tham chiếu tới giáo trình gốc.",
  },
  {
    icon: Presentation,
    title: "Slide trình chiếu",
    text: "Xem trực tuyến ở chế độ trình chiếu hoặc tải về file PowerPoint.",
  },
  {
    icon: ListChecks,
    title: "Quiz ôn tập",
    text: "Câu hỏi trắc nghiệm 4 lựa chọn, chấm điểm, giải thích và lưu lịch sử.",
  },
];

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center gap-12 px-4 py-16">
      <section className="flex flex-col items-start gap-6">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <BookOpenText className="size-5" /> Stugen
        </div>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
          Biến giáo trình PDF thành tóm tắt, slide và quiz ôn tập
        </h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Tải giáo trình lên, AI đọc theo từng chương và tạo học liệu cho bạn. Mọi bài giảng
          được lưu trong thư viện cá nhân để xem lại bất cứ lúc nào.
        </p>
        <Suspense>
          <LoginErrorNotice />
        </Suspense>
        <HomeActions />
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="rounded-xl border bg-card p-5">
            <Icon className="mb-3 size-6 text-primary" />
            <h2 className="mb-1 font-medium">{title}</h2>
            <p className="text-sm text-muted-foreground">{text}</p>
          </div>
        ))}
      </section>

      <p className="text-xs text-muted-foreground">
        Dự án phi thương mại, mã nguồn mở (AGPL-3.0). Nội dung do AI tạo, nên đối chiếu với
        giáo trình.
      </p>
    </main>
  );
}

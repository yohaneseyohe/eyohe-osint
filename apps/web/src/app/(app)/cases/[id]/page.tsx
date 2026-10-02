import { Suspense } from "react";
import { CaseWorkspace } from "@/components/cases/case-workspace";

export const metadata = { title: "Case" };

export default async function CasePage({ params }: PageProps<"/cases/[id]">) {
  const { id } = await params;
  return (
    <Suspense>
      <CaseWorkspace id={id} />
    </Suspense>
  );
}

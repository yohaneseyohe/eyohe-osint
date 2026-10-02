import { Suspense } from "react";
import { EvidencePage } from "@/components/evidence/evidence-page";

export const metadata = { title: "Evidence" };

export default function Page() {
  return (
    <Suspense>
      <EvidencePage />
    </Suspense>
  );
}

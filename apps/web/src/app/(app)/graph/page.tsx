import { Suspense } from "react";
import { GraphPage } from "@/components/graph/graph-page";

export const metadata = { title: "Graph" };

export default function Page() {
  return (
    <Suspense>
      <GraphPage />
    </Suspense>
  );
}

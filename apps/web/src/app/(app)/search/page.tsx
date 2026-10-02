import { Suspense } from "react";
import { QueryPlayground } from "@/components/search/query-playground";

export const metadata = { title: "Search" };

export default function SearchPage() {
  return (
    <Suspense>
      <QueryPlayground />
    </Suspense>
  );
}

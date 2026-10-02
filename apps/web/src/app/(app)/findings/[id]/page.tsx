import { FindingDetailView } from "@/components/findings/finding-detail";

export const metadata = { title: "Finding" };

export default async function FindingPage({ params }: PageProps<"/findings/[id]">) {
  const { id } = await params;
  return <FindingDetailView id={id} />;
}

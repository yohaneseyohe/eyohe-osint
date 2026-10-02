import { InvestigationDetailView } from "@/components/investigations/investigation-detail";

export const metadata = { title: "Investigation" };

export default async function InvestigationPage({ params }: PageProps<"/investigations/[id]">) {
  const { id } = await params;
  return <InvestigationDetailView id={id} />;
}

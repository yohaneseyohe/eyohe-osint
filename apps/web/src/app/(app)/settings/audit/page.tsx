import { Suspense } from "react";
import { SettingsPage } from "@/components/settings/settings-page";

export const metadata = { title: "Audit log" };

export default function AuditPage() {
  return (
    <Suspense>
      <SettingsPage initialTab="audit" />
    </Suspense>
  );
}

import { Suspense } from "react";
import { SettingsPage } from "@/components/settings/settings-page";

export const metadata = { title: "Settings" };

export default function Page() {
  return (
    <Suspense>
      <SettingsPage />
    </Suspense>
  );
}

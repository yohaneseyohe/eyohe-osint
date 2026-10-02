"use client";

import { useState } from "react";
import { Check, HelpCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { ReviewState } from "@/lib/types";

/** Accept / Reject / Needs verification with an optional analyst note; shared by evidence, findings and relationships. */
export function ReviewActions({
  onReview,
  pending,
  current,
  labels = { accept: "Accept", reject: "Reject", verify: "Needs verification" },
}: {
  onReview: (state: ReviewState, note: string) => void;
  pending?: boolean;
  current?: string;
  labels?: { accept: string; reject: string; verify: string };
}) {
  const [note, setNote] = useState("");
  const submit = (state: ReviewState) => {
    onReview(state, note);
    setNote("");
  };
  return (
    <div className="space-y-2">
      <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Review note (optional, recorded in the audit log)" rows={2} />
      <div className="flex flex-wrap gap-2">
        <Button variant="success" size="sm" onClick={() => submit("ACCEPTED")} disabled={pending || current === "ACCEPTED"}>
          <Check /> {labels.accept}
        </Button>
        <Button variant="destructive" size="sm" onClick={() => submit("REJECTED")} disabled={pending || current === "REJECTED"}>
          <X /> {labels.reject}
        </Button>
        <Button variant="warning" size="sm" onClick={() => submit("NEEDS_VERIFICATION")} disabled={pending || current === "NEEDS_VERIFICATION"}>
          <HelpCircle /> {labels.verify}
        </Button>
      </div>
    </div>
  );
}

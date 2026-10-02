"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Send } from "lucide-react";
import { ApiError, apiPost, errorMessage } from "@/lib/api";
import { useAiRetrieve } from "@/lib/queries";
import type { AIQueryResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { AnswerView, PassageList, useRefOpener } from "./answer-view";
import { LoadingState } from "@/components/shared/states";

/** Evidence-only Q&A for one case. Answers are rendered with their citations; nothing is shown without a source passage. */
export function AskPanel({ caseId, initialQuestion }: { caseId: string; initialQuestion?: string }) {
  const [question, setQuestion] = useState(initialQuestion ?? "");
  const [asked, setAsked] = useState<string | null>(null);
  const { open, dialogs } = useRefOpener();
  const ask = useMutation({
    mutationFn: (q: string) => apiPost<AIQueryResponse>("/ai/query", { case_id: caseId, question: q, mode: "ask" }),
  });
  const offline = ask.isError && ask.error instanceof ApiError && ask.error.code === "ollama_unavailable";
  // When the model is offline we still show what retrieval found, so the analyst can read the evidence directly.
  const fallback = useAiRetrieve(caseId, asked ?? "", offline);
  const [autoAsked, setAutoAsked] = useState(false);
  if (initialQuestion && !autoAsked) {
    setAutoAsked(true);
    setAsked(initialQuestion);
    ask.mutate(initialQuestion);
  }
  const submit = () => {
    const q = question.trim();
    if (!q) return;
    setAsked(q);
    ask.mutate(q);
  };

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Bot className="size-3.5" /> AI Analyst</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-fg-muted">Answers strictly from this case&apos;s evidence, citing evidence IDs. The model cannot add sources.</p>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask about the collected evidence…" aria-label="Question" />
          <Button type="submit" loading={ask.isPending} disabled={!question.trim()}><Send /> Ask</Button>
        </form>
        {ask.isPending ? <div className="space-y-2"><p className="text-xs text-fg-subtle">Retrieving passages and asking the local model (can take a while on CPU)…</p><LoadingState rows={3} /></div> : null}
        {ask.isError && !offline ? <p role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">{errorMessage(ask.error)}</p> : null}
        {offline ? (
          <div className="space-y-2">
            <p role="alert" className="rounded-md border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">AI is offline: {errorMessage(ask.error)} Showing the retrieved passages instead.</p>
            {fallback.isPending ? <LoadingState rows={3} /> : fallback.data ? <PassageList passages={fallback.data} onOpen={open} /> : null}
          </div>
        ) : null}
        {ask.data?.answer ? <AnswerView answer={ask.data.answer} onOpen={open} /> : null}
        {dialogs}
      </CardContent>
    </Card>
  );
}

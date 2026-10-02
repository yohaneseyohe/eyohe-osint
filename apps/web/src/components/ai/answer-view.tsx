"use client";

import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { AIAnswer, AIPassage } from "@/lib/types";
import { TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { EvidenceReviewDialog } from "@/components/evidence/evidence-review-dialog";
import { EntityDrawer } from "@/components/entities/entity-drawer";
import { SourceDrawer } from "@/components/sources/source-drawer";
import { CitationChip } from "./citation-chip";
import { cn } from "@/lib/utils";

const REF_RE = /\[([A-Z]{2,5}-[A-Z]{1,4}-\d{3,}|note:[0-9a-f-]{8,})\]/g;

type Opened = { ref: string; kind: string } | null;

/** Replaces [EYO-EV-000012]-style citations in text with chips; unknown refs stay plain. */
function CitedText({ text, kinds, onOpen }: { text: string; kinds: Map<string, string>; onOpen: (ref: string, kind: string) => void }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(REF_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push(text.slice(last, idx));
    const ref = m[1];
    const kind = kinds.get(ref) ?? (ref.startsWith("note:") ? "note" : "evidence");
    parts.push(<CitationChip key={`${ref}-${idx}`} refId={ref} kind={kind} onOpen={onOpen} className="mx-0.5" />);
    last = idx + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts.map((p, i) => <Fragment key={i}>{p}</Fragment>)}</>;
}

export function PassageList({ passages, onOpen }: { passages: AIPassage[]; onOpen: (ref: string, kind: string) => void }) {
  if (passages.length === 0) return <p className="text-xs text-fg-subtle">No passages retrieved.</p>;
  return (
    <ul className="space-y-1.5">
      {passages.map((p, i) => (
        <li key={`${p.ref}-${i}`} className="rounded-md border border-border bg-bg-elevated px-3 py-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <CitationChip refId={p.ref} kind={p.kind} onOpen={onOpen} />
            <TypeChip value={p.kind} />
            {typeof p.meta.confidence === "string" ? <span className="text-fg-subtle">{p.meta.confidence}</span> : null}
            {typeof p.score === "number" ? <Mono className="ml-auto text-fg-subtle">score {p.score.toFixed(2)}</Mono> : null}
          </div>
          <p className="mt-1 text-fg-muted">{p.text}</p>
        </li>
      ))}
    </ul>
  );
}

export function useRefOpener() {
  const [opened, setOpened] = useState<Opened>(null);
  const dialogs = (
    <>
      <EvidenceReviewDialog evidenceId={opened?.kind === "evidence" ? opened.ref : null} onClose={() => setOpened(null)} />
      <EntityDrawer entityId={opened?.kind === "entity" ? opened.ref : null} onClose={() => setOpened(null)} />
      <SourceDrawer sourceId={opened?.kind === "snapshot" ? opened.ref : null} onClose={() => setOpened(null)} />
    </>
  );
  return { open: (ref: string, kind: string) => setOpened({ ref, kind }), dialogs };
}

export function AnswerView({ answer, onOpen }: { answer: AIAnswer; onOpen: (ref: string, kind: string) => void }) {
  const [showPassages, setShowPassages] = useState(false);
  const kinds = new Map(answer.passages.concat(answer.citations).map((p) => [p.ref, p.kind]));
  const uncited = new Set(answer.uncited_sentences.map((s) => s.trim()));
  // Split into sentences so uncited ones can be flagged without altering the text.
  const sentences = answer.answer.split(/(?<=[.!?])\s+/);

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border bg-panel-2/40 px-4 py-3 text-sm leading-relaxed text-fg">
        {sentences.map((s, i) => {
          const flagged = uncited.has(s.trim());
          return (
            <span key={i} className={cn(flagged && "border-b border-dotted border-warning/70 text-fg-muted")} title={flagged ? "This sentence cites no evidence" : undefined}>
              <CitedText text={s} kinds={kinds} onOpen={onOpen} />{" "}
            </span>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-fg-subtle">
        <span>{answer.citations.length} citation{answer.citations.length === 1 ? "" : "s"}</span>
        {answer.uncited_sentences.length > 0 ? <span className="text-warning">· {answer.uncited_sentences.length} uncited sentence{answer.uncited_sentences.length === 1 ? "" : "s"} (dotted underline)</span> : null}
        {answer.model ? <Mono>· {answer.model}</Mono> : <span>· no model used</span>}
      </div>
      {answer.citations.length > 0 ? (
        <div className="flex flex-wrap gap-1">{answer.citations.map((c) => <CitationChip key={c.ref} refId={c.ref} kind={c.kind} onOpen={onOpen} />)}</div>
      ) : null}
      <button onClick={() => setShowPassages((v) => !v)} className="flex items-center gap-1 text-xs text-fg-muted hover:text-fg" aria-expanded={showPassages}>
        {showPassages ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />} Retrieved passages ({answer.passages.length})
      </button>
      {showPassages ? <PassageList passages={answer.passages} onOpen={onOpen} /> : null}
    </div>
  );
}

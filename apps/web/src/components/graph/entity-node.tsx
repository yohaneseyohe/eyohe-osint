"use client";

import { memo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { ENTITY_TYPE_COLOR } from "@/lib/labels";
import type { GraphNode } from "@/lib/types";
import { EntityIcon } from "@/components/entities/entity-icon";
import { cn, truncate } from "@/lib/utils";

export type EntityFlowNode = Node<{ node: GraphNode; dimmed: boolean }, "entity">;

function EntityNodeComponent({ data, selected }: NodeProps<EntityFlowNode>) {
  const n = data.node;
  const color = ENTITY_TYPE_COLOR[n.type] ?? "var(--slate)";
  return (
    <div
      className={cn(
        "glass flex items-center gap-2 rounded-md border px-2.5 py-1.5 shadow-md transition-opacity",
        n.is_target ? "border-accent ring-2 ring-accent/40" : "border-border",
        selected && "border-accent-bright",
        data.dimmed && "opacity-25",
      )}
      style={{ borderLeftColor: color, borderLeftWidth: 3 }}
      title={`${n.type}: ${n.value}`}
    >
      <Handle type="target" position={Position.Top} className="!size-1.5 !border-0 !bg-border-strong" />
      <EntityIcon type={n.type} className="size-3.5" />
      <div className="min-w-0 leading-tight">
        <div className={cn("font-mono text-[11px] text-fg", n.is_target && "font-semibold")}>{truncate(n.label || n.value, 28)}</div>
        <div className="text-[9px] uppercase tracking-wider text-fg-subtle">
          {n.type} · {n.evidence_count} ev
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!size-1.5 !border-0 !bg-border-strong" />
    </div>
  );
}

export const EntityNode = memo(EntityNodeComponent);

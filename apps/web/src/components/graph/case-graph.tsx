"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Edge,
  type NodeMouseHandler,
  type EdgeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Download, Search, Undo2 } from "lucide-react";
import { useGraph } from "@/lib/queries";
import { CONFIDENCE_STYLE, ENTITY_TYPE_COLOR } from "@/lib/labels";
import type { Confidence, GraphOut } from "@/lib/types";
import { cn, downloadJson } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { EntityIcon } from "@/components/entities/entity-icon";
import { EdgePanel } from "./edge-panel";
import { NodePanel as NodePanelLazy } from "./node-panel";
import { EntityNode, type EntityFlowNode } from "./entity-node";
import { radialLayout } from "./layout";

const nodeTypes = { entity: EntityNode };

function edgeStyle(confidence: string, reviewState: string): Partial<Edge> {
  const color = CONFIDENCE_STYLE[confidence as Confidence]?.color ?? "var(--slate)";
  const contradicted = confidence === "CONTRADICTED" || reviewState === "REJECTED";
  const weak = confidence === "POSSIBLE" || confidence === "UNVERIFIED" || confidence === "INFERENCE";
  const stroke = contradicted ? "var(--danger)" : color;
  return {
    style: { stroke, strokeWidth: contradicted ? 2 : 1.5, strokeDasharray: weak ? "5 4" : undefined, opacity: 0.85 },
    markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 14, height: 14 },
    labelStyle: { fill: "var(--fg-muted)", fontSize: 9, fontFamily: "var(--font-mono)" },
    labelBgStyle: { fill: "var(--panel)", fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 3,
  };
}

function Canvas({ caseId, data, focus, onFocus, onReset }: { caseId: string; data: GraphOut; focus: string | null; onFocus: (id: string) => void; onReset: () => void }) {
  const { fitView } = useReactFlow();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);

  const types = useMemo(() => [...new Set(data.nodes.map((n) => n.type))].sort(), [data.nodes]);

  const built = useMemo(() => {
    const pos = radialLayout(data.nodes, data.edges);
    const q = search.trim().toLowerCase();
    const visible = new Set(data.nodes.filter((n) => typeFilter.size === 0 || typeFilter.has(n.type)).map((n) => n.id));
    const nodes: EntityFlowNode[] = data.nodes
      .filter((n) => visible.has(n.id))
      .map((n) => ({
        id: n.id,
        type: "entity",
        position: { x: pos.get(n.id)?.x ?? 0, y: pos.get(n.id)?.y ?? 0 },
        data: { node: n, dimmed: q.length > 0 && !`${n.value} ${n.label} ${n.display_id}`.toLowerCase().includes(q) },
      }));
    const edges: Edge[] = data.edges
      .filter((e) => visible.has(e.source) && visible.has(e.target))
      .map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.type,
        ...edgeStyle(e.confidence, e.review_state),
      }));
    return { nodes, edges };
  }, [data, search, typeFilter]);

  const [nodes, setNodes, onNodesChange] = useNodesState<EntityFlowNode>(built.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(built.edges);

  useEffect(() => {
    setNodes(built.nodes);
    setEdges(built.edges);
    const t = window.setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 50);
    return () => window.clearTimeout(t);
  }, [built, setNodes, setEdges, fitView]);

  const onNodeClick: NodeMouseHandler<EntityFlowNode> = useCallback((_, n) => {
    setSelectedEdge(null);
    setSelectedNode(n.id);
  }, []);
  const onEdgeClick: EdgeMouseHandler = useCallback((_, e) => {
    setSelectedNode(null);
    setSelectedEdge(e.id);
  }, []);

  const toggleType = (t: string) =>
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });

  return (
    <div className="flex h-[calc(100vh-11rem)] min-h-[520px] overflow-hidden rounded-lg border border-border bg-bg">
      <div className="relative min-w-0 flex-1">
        <div className="absolute left-3 top-3 z-10 flex max-w-[calc(100%-1.5rem)] flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find node…" className="h-8 w-52 pl-8 text-xs" aria-label="Find node" />
          </div>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Filter node types">
            {types.map((t) => (
              <button
                key={t}
                onClick={() => toggleType(t)}
                aria-pressed={typeFilter.has(t)}
                className={cn(
                  "glass inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase",
                  typeFilter.size === 0 || typeFilter.has(t) ? "border-border text-fg-muted" : "border-border/40 text-fg-subtle opacity-50",
                  typeFilter.has(t) && "border-accent text-accent-bright",
                )}
                style={{ borderLeftColor: ENTITY_TYPE_COLOR[t], borderLeftWidth: 2 }}
              >
                <EntityIcon type={t} className="size-3" /> {t}
              </button>
            ))}
          </div>
        </div>
        <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
          {focus ? (
            <Button variant="secondary" size="xs" onClick={onReset}><Undo2 /> Full graph</Button>
          ) : null}
          <Button variant="secondary" size="xs" onClick={() => downloadJson(`eyohe-graph-${caseId.slice(0, 8)}.json`, data)}>
            <Download /> Export JSON
          </Button>
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onPaneClick={() => { setSelectedNode(null); setSelectedEdge(null); }}
          fitView
          minZoom={0.1}
          maxZoom={2.5}
          proOptions={{ hideAttribution: true }}
          nodesConnectable={false}
          deleteKeyCode={null}
        >
          <Background gap={24} size={1} color="var(--border)" />
          <Controls showInteractive={false} position="bottom-left" />
          <MiniMap pannable zoomable nodeColor={(n) => ENTITY_TYPE_COLOR[(n as EntityFlowNode).data.node.type] ?? "#475569"} maskColor="rgba(7,11,20,0.7)" />
        </ReactFlow>
        <div className="pointer-events-none absolute bottom-3 right-3 z-10 flex gap-3 rounded-md border border-border bg-panel/80 px-2.5 py-1.5 text-[10px] text-fg-muted">
          <span className="flex items-center gap-1"><span className="inline-block h-px w-5 bg-success" /> confirmed</span>
          <span className="flex items-center gap-1"><span className="inline-block h-px w-5 border-t border-dashed border-slate" /> possible / unverified</span>
          <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-5 bg-danger" /> contradicted</span>
          <span className="font-mono">{data.nodes.length} nodes · {data.edges.length} edges</span>
        </div>
      </div>
      {selectedNode ? (
        <NodePanelLazy entityId={selectedNode} onClose={() => setSelectedNode(null)} onExpand={onFocus} onSelectEdge={(id) => { setSelectedNode(null); setSelectedEdge(id); }} />
      ) : null}
      {selectedEdge ? <EdgePanel relationshipId={selectedEdge} caseId={caseId} onClose={() => setSelectedEdge(null)} /> : null}
    </div>
  );
}

export function CaseGraph({ caseId, initialEntityId }: { caseId: string; initialEntityId?: string | null }) {
  const [focus, setFocus] = useState<string | null>(initialEntityId ?? null);
  const [depth] = useState(2);
  const query = useGraph(caseId, focus ? { entity_id: focus, depth } : undefined);

  if (query.isPending) return <LoadingState rows={8} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (query.data.nodes.length === 0) {
    return <EmptyState title="No graph yet" description="Entities and relationships appear here after an investigation correlates its evidence." />;
  }
  return (
    <ReactFlowProvider>
      <Canvas caseId={caseId} data={query.data} focus={focus} onFocus={setFocus} onReset={() => setFocus(null)} />
    </ReactFlowProvider>
  );
}

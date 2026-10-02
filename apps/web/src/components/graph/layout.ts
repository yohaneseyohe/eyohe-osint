import type { GraphEdge, GraphNode } from "@/lib/types";

export interface Positioned {
  id: string;
  x: number;
  y: number;
}

/**
 * Deterministic client-side layout: targets in the centre, other nodes on
 * concentric rings grouped by type, ordered by degree so hubs sit together.
 * No physics, so the picture is stable between refetches.
 */
export function radialLayout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Positioned> {
  const degree = new Map<string, number>();
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  const out = new Map<string, Positioned>();
  const targets = nodes.filter((n) => n.is_target);
  const rest = nodes.filter((n) => !n.is_target);

  // Centre cluster for targets.
  targets.forEach((n, i) => {
    if (targets.length === 1) out.set(n.id, { id: n.id, x: 0, y: 0 });
    else {
      const a = (2 * Math.PI * i) / targets.length;
      out.set(n.id, { id: n.id, x: Math.cos(a) * 120, y: Math.sin(a) * 120 });
    }
  });

  // Group remaining nodes by type, then lay the groups out on rings in contiguous arcs.
  const byType = new Map<string, GraphNode[]>();
  for (const n of rest) byType.set(n.type, [...(byType.get(n.type) ?? []), n]);
  const ordered = [...byType.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .flatMap(([, ns]) => ns.sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0)));

  const perRing = 18;
  let ringIndex = 0;
  let placed = 0;
  while (placed < ordered.length) {
    const count = Math.min(perRing + ringIndex * 10, ordered.length - placed);
    const radius = 320 + ringIndex * 240;
    for (let i = 0; i < count; i++) {
      const n = ordered[placed + i];
      const a = (2 * Math.PI * i) / count - Math.PI / 2 + ringIndex * 0.2;
      out.set(n.id, { id: n.id, x: Math.cos(a) * radius, y: Math.sin(a) * radius });
    }
    placed += count;
    ringIndex += 1;
  }
  return out;
}

"use client";

import { useMutation } from "@tanstack/react-query";

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  provider: string;
}

/**
 * Query Playground hook. The OpenAPI spec has no POST /api/v1/search yet, so this
 * resolves to a "not available" marker instead of calling the API.
 * TODO(phase-3): replace the mutationFn with `apiPost<SearchResult[]>("/search", { q, providers })`.
 */
export function useSearch() {
  return useMutation({
    mutationFn: async (q: string): Promise<{ available: false; results: SearchResult[] }> => {
      void q; // kept so the call signature matches the future API
      return { available: false, results: [] };
    },
  });
}

export const SEARCH_AVAILABLE = false;

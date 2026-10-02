import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Density = "comfortable" | "compact";

interface UiState {
  sidebarCollapsed: boolean;
  density: Density;
  selectedCaseId: string | null;
  feedPaused: boolean;
  toggleSidebar: () => void;
  setDensity: (d: Density) => void;
  setSelectedCaseId: (id: string | null) => void;
  setFeedPaused: (paused: boolean) => void;
}

// UI-only state; all domain data lives in TanStack Query.
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      density: "comfortable",
      selectedCaseId: null,
      feedPaused: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setDensity: (density) => set({ density }),
      setSelectedCaseId: (selectedCaseId) => set({ selectedCaseId }),
      setFeedPaused: (feedPaused) => set({ feedPaused }),
    }),
    {
      name: "eyohe-ui",
      partialize: (s) => ({
        sidebarCollapsed: s.sidebarCollapsed,
        density: s.density,
        selectedCaseId: s.selectedCaseId,
      }),
    },
  ),
);

"use client";

import * as React from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { create } from "zustand";
import { cn } from "@/lib/utils";

type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  title: string;
  description?: string;
}

interface ToastStore {
  toasts: ToastItem[];
  push: (t: Omit<ToastItem, "id">) => void;
  dismiss: (id: number) => void;
}

let counter = 0;

const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: (t) => set((s) => ({ toasts: [...s.toasts.slice(-4), { ...t, id: ++counter }] })),
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}));

/** Imperative toast API so mutations can report without threading props. */
export const toast = {
  success: (title: string, description?: string) => useToastStore.getState().push({ kind: "success", title, description }),
  error: (title: string, description?: string) => useToastStore.getState().push({ kind: "error", title, description }),
  info: (title: string, description?: string) => useToastStore.getState().push({ kind: "info", title, description }),
};

const ICONS: Record<ToastKind, React.ReactNode> = {
  success: <CheckCircle2 className="size-4 text-success" />,
  error: <AlertTriangle className="size-4 text-danger" />,
  info: <Info className="size-4 text-accent-bright" />,
};

export function Toaster() {
  const { toasts, dismiss } = useToastStore();
  return (
    <ToastPrimitive.Provider swipeDirection="right" duration={5000}>
      {toasts.map((t) => (
        <ToastPrimitive.Root
          key={t.id}
          onOpenChange={(open) => !open && dismiss(t.id)}
          className={cn(
            "group pointer-events-auto relative flex w-full items-start gap-3 rounded-lg border border-border bg-panel p-3 pr-8 shadow-xl animate-slide-in data-[swipe=end]:animate-fade-in",
            t.kind === "error" && "border-danger/40",
          )}
        >
          <span className="mt-0.5">{ICONS[t.kind]}</span>
          <div className="min-w-0">
            <ToastPrimitive.Title className="text-sm font-medium text-fg">{t.title}</ToastPrimitive.Title>
            {t.description ? (
              <ToastPrimitive.Description className="mt-0.5 text-xs text-fg-muted break-words">
                {t.description}
              </ToastPrimitive.Description>
            ) : null}
          </div>
          <ToastPrimitive.Close className="absolute right-2 top-2 rounded p-0.5 text-fg-subtle hover:text-fg" aria-label="Dismiss">
            <X className="size-3.5" />
          </ToastPrimitive.Close>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2 outline-none" />
    </ToastPrimitive.Provider>
  );
}

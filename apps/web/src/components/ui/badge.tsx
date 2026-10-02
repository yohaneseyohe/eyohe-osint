import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-none tracking-wide whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "border-border-strong bg-panel-2 text-fg-muted",
        accent: "border-info/30 bg-info/15 text-accent-bright",
        outline: "border-border text-fg-muted",
        success: "border-success/30 bg-success/15 text-success",
        warning: "border-warning/30 bg-warning/15 text-warning",
        danger: "border-danger/30 bg-danger/15 text-danger",
        violet: "border-violet/30 bg-violet/15 text-violet",
        demo: "border-warning/40 bg-warning/10 text-warning font-semibold",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

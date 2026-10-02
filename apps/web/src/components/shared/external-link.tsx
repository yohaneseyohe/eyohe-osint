import { ExternalLink as Icon } from "lucide-react";
import { Mono } from "./mono";
import { cn, truncate } from "@/lib/utils";

export function ExternalLink({ href, max = 80, className }: { href: string; max?: number; className?: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className={cn("inline-flex max-w-full items-center gap-1 text-accent-bright hover:underline underline-offset-2", className)}
    >
      <Mono className="truncate">{truncate(href, max)}</Mono>
      <Icon className="size-3 shrink-0 opacity-70" />
    </a>
  );
}

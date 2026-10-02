import { AtSign, Bitcoin, Building2, Calendar, FileText, Globe, GitBranch, Hash, Link2, MapPin, Newspaper, Phone, Server, User, UserCircle } from "lucide-react";
import { ENTITY_TYPE_COLOR } from "@/lib/labels";
import { cn } from "@/lib/utils";

const ICONS: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  PERSON: User,
  USERNAME: AtSign,
  EMAIL: AtSign,
  DOMAIN: Globe,
  IP: Server,
  URL: Link2,
  ORGANIZATION: Building2,
  COMPANY: Building2,
  LOCATION: MapPin,
  PHONE: Phone,
  SOCIAL_ACCOUNT: UserCircle,
  REPOSITORY: GitBranch,
  DOCUMENT: FileText,
  ARTICLE: Newspaper,
  EVENT: Calendar,
  CRYPTO_ADDRESS: Bitcoin,
};

export function EntityIcon({ type, className }: { type: string; className?: string }) {
  const Icon = ICONS[type] ?? Hash;
  return <Icon className={cn("size-4 shrink-0", className)} style={{ color: ENTITY_TYPE_COLOR[type] ?? "var(--slate)" }} />;
}

export const ENTITY_TYPES = Object.keys(ICONS);

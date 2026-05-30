import { kindBadgeClass, managedBadge, managedLabel } from "@/lib/utils";

interface NodeBadgeProps {
  kind: string;
  managed: boolean;
}

export function NodeBadge({ kind, managed }: NodeBadgeProps) {
  return (
    <span className="flex gap-1 items-center flex-wrap">
      <span className={`badge badge-sm ${kindBadgeClass(kind)}`}>{kind}</span>
      <span className={`badge badge-sm ${managedBadge(managed)}`}>
        {managedLabel(managed)}
      </span>
    </span>
  );
}

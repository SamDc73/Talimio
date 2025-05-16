import { TagChip } from "./TagChip"

export function TagList({ tags, colorClass }) {
  return (
    <div className="flex flex-wrap gap-1 mb-4">
      {tags.slice(0, 2).map((tag) => (
        <TagChip key={tag} tag={tag} colorClass={colorClass} />
      ))}
      {tags.length > 2 && (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
          +{tags.length - 2}
        </span>
      )}
    </div>
  )
}
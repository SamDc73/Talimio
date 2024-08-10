import { useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/apiClient"
import { BaseCard } from "./BaseCard"

/**
 * Content card with hover prefetch optimization
 * Prefetches progress data on hover for instant loading
 */
export function PrefetchContentCard({ id, title, description, type, children, ...props }) {
	const queryClient = useQueryClient()

	const handleMouseEnter = () => {
		// Prefetch progress data on hover
		queryClient.prefetchQuery({
			queryKey: ["progress", [id]],
			queryFn: async () => {
				const response = await api.post("/progress/batch", {
					content_ids: [id],
				})
				return response || {}
			},
			staleTime: 30 * 1000, // 30 seconds
		})
	}

	return (
		<BaseCard onMouseEnter={handleMouseEnter} {...props}>
			{children || (
				<div className="space-y-4">
					{/* Content type badge */}
					<div className="flex items-center justify-between">
						<span
							className={`
              inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
              ${type === "course" ? "bg-teal-50 text-teal-600" : ""}
              ${type === "book" ? "bg-blue-50 text-blue-600" : ""}
              ${type === "youtube" ? "bg-violet-50 text-violet-600" : ""}
              ${type === "flashcards" ? "bg-amber-50 text-amber-600" : ""}
            `}
						>
							{type}
						</span>
					</div>

					{/* Title and description */}
					<div>
						<h3 className="text-lg font-semibold text-gray-900 mb-1">{title}</h3>
						{description && <p className="text-sm text-gray-600 line-clamp-2">{description}</p>}
					</div>
				</div>
			)}
		</BaseCard>
	)
}

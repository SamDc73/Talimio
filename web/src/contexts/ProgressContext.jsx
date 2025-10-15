import { useQueryClient } from "@tanstack/react-query"
import { createContext, useContext, useEffect } from "react"

export const ProgressContext = createContext()

/**
 * Provider for unified progress state management
 * Listens for progress updates from any source and syncs with React Query cache
 */
export function ProgressProvider({ children }) {
	const queryClient = useQueryClient()

	// Listen for progress updates from any source
	useEffect(() => {
		const handleProgressUpdate = (event) => {
			const detail = event?.detail || {}
			const { contentId, progress, metadata } = detail

			if (!contentId) {
				return
			}

			queryClient.setQueriesData({ queryKey: ["progress"], exact: false }, (old) => {
				const base = old && typeof old === "object" ? old : {}
				const previousEntry = base[contentId]
				const previousMetadata =
					previousEntry && typeof previousEntry === "object" && !Array.isArray(previousEntry)
						? previousEntry.metadata || {}
						: {}
				const resolvedProgress =
					progress ?? (typeof previousEntry === "number" ? previousEntry : (previousEntry?.progress_percentage ?? 0))

				return {
					...base,
					[contentId]: {
						progress_percentage: resolvedProgress,
						metadata: metadata ? { ...previousMetadata, ...metadata } : previousMetadata,
					},
				}
			})
		}

		window.addEventListener("progressUpdated", handleProgressUpdate)

		return () => {
			window.removeEventListener("progressUpdated", handleProgressUpdate)
		}
	}, [queryClient])

	return <ProgressContext value={{}}>{children}</ProgressContext>
}

export function useProgressContext() {
	const context = useContext(ProgressContext)
	if (context === undefined) {
		throw new Error("useProgressContext must be used within a ProgressProvider")
	}
	return context
}

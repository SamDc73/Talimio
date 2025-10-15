import { useCallback, useEffect, useState } from "react"

import useAppStore from "@/stores/useAppStore"

export const useAppState = () => {
	const [currentRoadmapId, setCurrentRoadmapId] = useState(null)
	const [isLoading, _setIsLoading] = useState(false)

	// Zustand store selectors and actions
	const activeRoadmapId = useAppStore((state) => state.preferences?.userPreferences?.roadmapId || null)
	const userPreferences = useAppStore((state) => state.preferences?.userPreferences || null)
	const updatePreference = useAppStore((state) => state.updatePreference)

	// Create a setActiveRoadmap function using updatePreference
	const setActiveRoadmap = useCallback(
		(roadmapId) => {
			const currentPrefs = userPreferences || {}
			updatePreference("userPreferences", {
				...currentPrefs,
				roadmapId: roadmapId,
			})
		},
		[updatePreference, userPreferences]
	)

	const handleResetRoadmap = useCallback(() => {
		// Reset in Zustand store
		setActiveRoadmap(null)
		updatePreference("userPreferences", null)
		setCurrentRoadmapId(null)
	}, [setActiveRoadmap, updatePreference])

	// Check for existing roadmap on mount
	useEffect(() => {
		// Check Zustand store
		if (activeRoadmapId) {
			setCurrentRoadmapId(activeRoadmapId)
		}
	}, [activeRoadmapId])

	return {
		currentRoadmapId,
		isLoading,
		handleResetRoadmap,
		activeRoadmapId,
	}
}

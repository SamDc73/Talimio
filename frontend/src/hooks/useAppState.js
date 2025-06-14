import { useCallback, useEffect, useState } from "react";

import { STORAGE_KEYS } from "@/features/onboarding";
import { useOnboarding } from "@/features/onboarding/useOnboarding";
import { useToast } from "@/hooks/use-toast";
import useAppStore from "@/stores/useAppStore";

export const useAppState = () => {
	const [showOnboarding, setShowOnboarding] = useState(false);
	const [currentRoadmapId, setCurrentRoadmapId] = useState(null);
	const [isLoading, setIsLoading] = useState(false);

	const { resetOnboarding } = useOnboarding();
	const { toast } = useToast();

	// Zustand store selectors and actions
	const activeRoadmapId = useAppStore(
		(state) => state.roadmaps.activeRoadmapId,
	);
	const userPreferences = useAppStore(
		(state) => state.preferences.userPreferences,
	);
	const onboardingCompleted = useAppStore(
		(state) => state.preferences.onboardingCompleted,
	);
	const setActiveRoadmap = useAppStore((state) => state.setActiveRoadmap);
	const updatePreference = useAppStore((state) => state.updatePreference);

	// Check for existing roadmap on mount
	useEffect(() => {
		// First check Zustand store
		if (activeRoadmapId && onboardingCompleted) {
			setCurrentRoadmapId(activeRoadmapId);
			setShowOnboarding(false);
			return;
		}

		// Migration: Move data from localStorage to Zustand if needed
		const savedRoadmap = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
		if (savedRoadmap && !activeRoadmapId) {
			try {
				const preferences = JSON.parse(savedRoadmap);
				if (preferences?.roadmapId) {
					// Migrate to Zustand store
					setActiveRoadmap(preferences.roadmapId);
					updatePreference("onboardingCompleted", true);
					updatePreference("userPreferences", preferences);
					// Clean up localStorage after migration
					localStorage.removeItem(STORAGE_KEYS.USER_PREFERENCES);
					console.log("Migrated onboarding preferences to Zustand");
				}
			} catch (error) {
				console.error("Failed to migrate saved roadmap:", error);
				handleResetOnboarding();
			}
		}
	}, [
		activeRoadmapId,
		onboardingCompleted,
		setActiveRoadmap,
		updatePreference,
	]);

	const handleResetOnboarding = useCallback(() => {
		// Reset in Zustand store
		setActiveRoadmap(null);
		updatePreference("onboardingCompleted", false);
		updatePreference("userPreferences", null);
		setShowOnboarding(true);
		setCurrentRoadmapId(null);
		resetOnboarding();

		toast({
			title: "Reset Complete",
			description: "Starting fresh with a new roadmap.",
		});
	}, [resetOnboarding, toast, setActiveRoadmap, updatePreference]);

	const handleOnboardingComplete = async (answers) => {
		if (isLoading) return;

		console.log("Starting onboarding completion with answers:", answers);
		setIsLoading(true);

		try {
			// Prepare roadmap data
			const roadmapData = {
				title: answers.topic ? `${answers.topic} Learning Path` : "",
				description: answers.topic
					? `A personalized learning path for ${answers.topic}`
					: "",
				skillLevel: String(answers.skillLevel || "beginner").toLowerCase(), // Make sure it's a string
			};

			console.log("Sending roadmap creation request:", roadmapData);

			// Create roadmap
			const response = await fetch("http://localhost:8080/api/v1/roadmaps", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify(roadmapData),
			});

			// Log response details
			console.log("Roadmap creation response status:", response.status);
			const responseText = await response.text();
			console.log("Roadmap creation response:", responseText);

			if (!response.ok) {
				throw new Error(
					`Failed to create roadmap: ${response.status} - ${responseText}`,
				);
			}

			let newRoadmap;
			try {
				newRoadmap = JSON.parse(responseText);
			} catch (e) {
				console.error("Failed to parse roadmap response:", e);
				throw new Error("Invalid response from server");
			}

			console.log("Created roadmap:", newRoadmap);

			// Save preferences to Zustand store
			const preferences = {
				...answers,
				roadmapId: newRoadmap.id,
				timestamp: Date.now(),
			};

			console.log("Saving preferences to Zustand:", preferences);

			// Update Zustand store
			setActiveRoadmap(newRoadmap.id);
			updatePreference("onboardingCompleted", true);
			updatePreference("userPreferences", preferences);

			// Update local state
			setCurrentRoadmapId(newRoadmap.id);
			setShowOnboarding(false);

			toast({
				title: "Roadmap Created",
				description: "Your learning path is ready!",
			});

			return newRoadmap;
		} catch (error) {
			console.error("Failed to complete onboarding:", error);

			toast({
				title: "Error",
				description:
					error.message || "Failed to create roadmap. Please try again.",
				variant: "destructive",
			});

			// Reset state on error
			setCurrentRoadmapId(null);
			setShowOnboarding(true);

			throw error;
		} finally {
			setIsLoading(false);
		}
	};

	return {
		showOnboarding,
		currentRoadmapId,
		isLoading,
		handleOnboardingComplete,
		handleResetOnboarding,
	};
};

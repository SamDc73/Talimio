import { useCallback, useEffect, useState } from "react";

import { STORAGE_KEYS } from "@/features/onboarding";
import { useOnboarding } from "@/features/onboarding/useOnboarding";
import { useToast } from "@/hooks/use-toast";

export const useAppState = () => {
	const [showOnboarding, setShowOnboarding] = useState(false);
	const [currentRoadmapId, setCurrentRoadmapId] = useState(null);
	const [isLoading, setIsLoading] = useState(false);

	const { resetOnboarding } = useOnboarding();
	const { toast } = useToast();

	// Check for existing roadmap on mount
	useEffect(() => {
		const savedRoadmap = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
		if (savedRoadmap) {
			try {
				const preferences = JSON.parse(savedRoadmap);
				if (preferences?.roadmapId) {
					setCurrentRoadmapId(preferences.roadmapId);
					setShowOnboarding(false);
				}
			} catch (error) {
				console.error("Failed to parse saved roadmap:", error);
				handleResetOnboarding();
			}
		}
	}, []);

	const handleResetOnboarding = useCallback(() => {
		localStorage.removeItem(STORAGE_KEYS.USER_PREFERENCES);
		setShowOnboarding(true);
		setCurrentRoadmapId(null);
		resetOnboarding();

		toast({
			title: "Reset Complete",
			description: "Starting fresh with a new roadmap.",
		});
	}, [resetOnboarding, toast]);

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

			// Save preferences
			const preferences = {
				...answers,
				roadmapId: newRoadmap.id,
				timestamp: Date.now(),
			};

			console.log("Saving preferences:", preferences);
			localStorage.setItem(
				STORAGE_KEYS.USER_PREFERENCES,
				JSON.stringify(preferences),
			);

			// Update state
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

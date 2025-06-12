import { useState } from "react";

import { STORAGE_KEYS } from "@/features/onboarding";
import { useApi } from "@/hooks/useApi";
import useAppStore from "@/stores/useAppStore";

export function useOnboarding() {
	const { execute: fetchRoadmap } = useApi("/api/v1/roadmaps", {
		method: "GET",
	});
	const [topic, setTopic] = useState("");

	// Zustand store actions for user preferences
	const updatePreference = useAppStore((state) => state.updatePreference);
	const setActiveRoadmap = useAppStore((state) => state.setActiveRoadmap);

	const { execute: fetchQuestions } = useApi("/api/v1/onboarding/questions", {
		method: "POST",
	});

	const { execute: savePreferences } = useApi("/api/onboarding", {
		method: "POST",
	});

	const getQuestions = async (topic) => {
		try {
			const response = await fetchQuestions({ topic });
			return response.questions || []; // Ensure we always return an array
		} catch (error) {
			console.error("Failed to fetch questions:", error);
			return [];
		}
	};

	const submitOnboarding = async (answers) => {
		try {
			const response = await savePreferences(answers);

			// Save to Zustand store instead of localStorage
			if (response.roadmapId) {
				setActiveRoadmap(response.roadmapId);
				updatePreference("onboardingCompleted", true);
				updatePreference("userPreferences", response);
			}

			// Also save to localStorage temporarily for backwards compatibility
			localStorage.setItem(
				STORAGE_KEYS.USER_PREFERENCES,
				JSON.stringify(response),
			);
			return response;
		} catch (error) {
			console.error("Failed to save onboarding preferences:", error);
			const fallbackResponse = answers;

			// Save fallback to store
			if (fallbackResponse.roadmapId) {
				setActiveRoadmap(fallbackResponse.roadmapId);
				updatePreference("onboardingCompleted", true);
				updatePreference("userPreferences", fallbackResponse);
			}

			// Also save to localStorage temporarily for backwards compatibility
			localStorage.setItem(
				STORAGE_KEYS.USER_PREFERENCES,
				JSON.stringify(fallbackResponse),
			);
			return fallbackResponse;
		}
	};

	const fetchRoadmapAfterOnboarding = async (roadmapId) => {
		try {
			const response = await fetchRoadmap({
				params: { roadmapId: roadmapId },
			});
			return response;
		} catch (error) {
			console.error("Failed to fetch roadmap:", error);
			return null;
		}
	};

	const resetOnboarding = () => {
		// Clear from store
		setActiveRoadmap(null);
		updatePreference("onboardingCompleted", false);
		updatePreference("userPreferences", null);

		// Also clear localStorage for backwards compatibility
		localStorage.removeItem(STORAGE_KEYS.USER_PREFERENCES);
		setTopic("");
		return true;
	};

	return {
		topic,
		setTopic,
		getQuestions,
		submitOnboarding,
		resetOnboarding,
		fetchRoadmapAfterOnboarding,
	};
}

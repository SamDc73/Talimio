import { useState, useEffect, useCallback } from 'react';
import { STORAGE_KEYS } from '@/features/onboarding';
import { useOnboarding } from '@/features/onboarding/useOnboarding';
import { useRoadmap } from '@/hooks/useRoadmap';
import { useToast } from '@/hooks/use-toast';

export const useAppState = () => {
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [userPreferences, setUserPreferences] = useState(null);
  const [currentRoadmapId, setCurrentRoadmapId] = useState(null);

  const { createRoadmap } = useRoadmap();
  const { resetOnboarding } = useOnboarding();
  const { toast } = useToast();

  useEffect(() => {
    const checkOnboarding = () => {
      const savedPreferences = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
      if (savedPreferences) {
        try {
          const preferences = JSON.parse(savedPreferences);
          setUserPreferences(preferences);
          setCurrentRoadmapId(preferences.roadmapId);
          setShowOnboarding(false);
        } catch (error) {
          console.error('Failed to parse preferences:', error);
          handleResetOnboarding();
        }
      }
    };

    checkOnboarding();
  }, []);

  const handleOnboardingComplete = async (answers) => {
    try {
      if (!answers || !answers.topic) {
        throw new Error('Invalid onboarding answers');
      }

      const skillLevel = answers.skill_level || 'beginner';

      const roadmapData = {
        title: `${answers.topic} Learning Path`,
        description: `A personalized learning path for ${answers.topic}`,
        skill_level: skillLevel
      };

      const newRoadmap = await createRoadmap(roadmapData);

      if (!newRoadmap?.id) {
        throw new Error('Failed to create roadmap: No ID returned');
      }

      const preferences = {
        ...answers,
        roadmapId: newRoadmap.id
      };

      localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(preferences));
      setUserPreferences(preferences);
      setCurrentRoadmapId(newRoadmap.id);
      setShowOnboarding(false);

      toast({
        title: "Welcome!",
        description: `Your ${answers.topic} roadmap has been created!`,
      });

      return newRoadmap;
    } catch (error) {
      console.error('Failed to create roadmap:', error);
      toast({
        title: "Error",
        description: "Failed to create your roadmap. Please try again.",
        variant: "destructive"
      });
      throw error;
    }
  };

  const handleResetOnboarding = useCallback(() => {
    resetOnboarding();
    localStorage.removeItem(STORAGE_KEYS.USER_PREFERENCES);
    setShowOnboarding(true);
    setUserPreferences(null);
    setCurrentRoadmapId(null);

    toast({
      title: "Onboarding Reset",
      description: "You can now go through the onboarding process again.",
    });
  }, [resetOnboarding, toast]);

  return {
    showOnboarding,
    userPreferences,
    currentRoadmapId,
    handleOnboardingComplete,
    handleResetOnboarding
  };
};

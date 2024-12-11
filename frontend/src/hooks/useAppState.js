import { useState, useEffect, useCallback } from 'react';
import { STORAGE_KEYS } from '@/features/onboarding';
import { useOnboarding } from '@/features/onboarding/useOnboarding';
import { useToast } from '@/hooks/use-toast';

export const useAppState = () => {
  const [showOnboarding, setShowOnboarding] = useState(true);
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
        console.error('Failed to parse saved roadmap:', error);
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

  const createRoadmapWithNodes = async (roadmapData) => {
    // Create roadmap
    const response = await fetch('http://localhost:8080/api/v1/roadmaps', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(roadmapData)
    });

    if (!response.ok) {
      throw new Error(`Failed to create roadmap: ${response.statusText}`);
    }

    const newRoadmap = await response.json();
    return newRoadmap;
  };

  const createNode = async (roadmapId, nodeData) => {
    const response = await fetch(`http://localhost:8080/api/v1/roadmaps/${roadmapId}/nodes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(nodeData)
    });

    if (!response.ok) {
      throw new Error(`Failed to create node: ${response.statusText}`);
    }

    return await response.json();
  };

  const handleOnboardingComplete = async (answers) => {
    console.log("handleOnboardingComplete called with:", answers); // Debug log

    if (isLoading) return;

    setIsLoading(true);
    try {
      const roadmapData = {
        title: `${answers.topic} Learning Path`,
        description: `A personalized learning path for ${answers.topic}`,
        skill_level: answers.skill_level || 'beginner'
      };

      console.log("Sending roadmapData:", roadmapData); // Debug log

      const response = await fetch('http://localhost:8080/api/v1/roadmaps', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(roadmapData)
      });

      if (!response.ok) {
        throw new Error('Failed to create roadmap');
      }

      const newRoadmap = await response.json();
      console.log("Received newRoadmap:", newRoadmap); // Debug log

      const preferences = {
        ...answers,
        roadmapId: newRoadmap.id,
        timestamp: Date.now()
      };

      localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(preferences));
      setCurrentRoadmapId(newRoadmap.id);
      setShowOnboarding(false);

      return newRoadmap;
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
      toast({
        title: "Error",
        description: "Failed to create roadmap. Please try again.",
        variant: "destructive"
      });
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
    handleResetOnboarding
  };
};

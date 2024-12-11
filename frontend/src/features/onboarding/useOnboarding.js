import { useState } from 'react';

import { STORAGE_KEYS } from '@/features/onboarding';
import { useApi } from '@/hooks/useApi';
import { MOCK_ONBOARDING_DATA } from '@/lib/mock-data/onboarding';

export function useOnboarding() {
  const { execute: fetchRoadmap } = useApi('/api/v1/roadmaps', { method: 'GET' });
  const [topic, setTopic] = useState('');

  const {
    execute: fetchQuestions
  } = useApi('/api/v1/onboarding/questions', {
    method: 'POST',
  });

  const {
    execute: savePreferences
  } = useApi('/api/onboarding', {
    method: 'POST',
    fallbackData: MOCK_ONBOARDING_DATA.defaultAnswers
  });

  const getQuestions = async (topic) => {
    try {
      const response = await fetchQuestions({ topic });
      return response.questions || [];  // Ensure we always return an array
    } catch (error) {
      console.error('Failed to fetch questions:', error);
      return [];
    }
  };

  const submitOnboarding = async (answers) => {
    try {
      const response = await savePreferences(answers);
      localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(response));
      return response;
    } catch (error) {
      console.error('Failed to save onboarding preferences:', error);
      const fallbackResponse = {
        ...MOCK_ONBOARDING_DATA.defaultAnswers,
        ...answers
      };
      localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(fallbackResponse));
      return fallbackResponse;
    }
  };

  const fetchRoadmapAfterOnboarding = async (roadmapId) => {
    try {
      const response = await fetchRoadmap({ params: { roadmap_id: roadmapId } });
      return response;
    } catch (error) {
      console.error('Failed to fetch roadmap:', error);
      return null;
    }
  };

  const resetOnboarding = () => {
    localStorage.removeItem(STORAGE_KEYS.USER_PREFERENCES);
    setTopic('');
    return true;
  };

  return {
    topic,
    setTopic,
    getQuestions,
    submitOnboarding,
    resetOnboarding,
    fetchRoadmapAfterOnboarding
  };
}

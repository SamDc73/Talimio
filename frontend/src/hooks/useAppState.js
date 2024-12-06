import { useState, useEffect } from 'react';

import { STORAGE_KEYS } from '@/features/onboarding';
import { useOnboarding } from '@/features/onboarding/useOnboarding';
import { useToast } from '@/hooks/use-toast';

export const useAppState = () => {
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [userPreferences, setUserPreferences] = useState(null);
  const { resetOnboarding } = useOnboarding();
  const { toast } = useToast();
  
  useEffect(() => {
    checkOnboardingStatus();
  }, []);

  const checkOnboardingStatus = () => {
    const savedPreferences = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
    if (!savedPreferences) {
      setShowOnboarding(true);
    } else {
      setUserPreferences(JSON.parse(savedPreferences));
    }
  };

  const handleOnboardingComplete = (answers) => {
    setUserPreferences(answers);
    setShowOnboarding(false);
    toast({
      title: "Welcome!",
      description: `Great to have you here, ${answers.name}!`,
    });
  };

  const handleResetOnboarding = () => {
    resetOnboarding();
    setShowOnboarding(true);
    setUserPreferences(null);
    toast({
      title: "Onboarding Reset",
      description: "You can now go through the onboarding process again.",
    });
  };

  return {
    showOnboarding,
    userPreferences,
    handleOnboardingComplete,
    handleResetOnboarding,
  };
};

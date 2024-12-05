import { OnboardingFlow as OnboardingComponent } from './index.jsx';
import { useOnboarding } from './useOnboarding';
import { useOnboardingState } from './useOnboardingState';

// Constants
export const STORAGE_KEYS = {
  USER_PREFERENCES: 'userPreferences',
};

// Re-export hooks and utilities
export {
  useOnboarding,
  useOnboardingState,
};

// Export the main component as OnboardingFlow
export const OnboardingFlow = OnboardingComponent;

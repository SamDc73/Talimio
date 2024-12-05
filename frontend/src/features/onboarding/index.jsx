import React from 'react';
import { Progress } from '@/components/progress';
import { Button } from '@/components/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/dialog';
import { TextInput } from './TextInput';
import { OptionCards } from './OptionCards';
import { useOnboardingState } from './useOnboardingState';

export const OnboardingFlow = ({ isOpen, onComplete }) => {
  const {
    currentQuestion,
    currentAnswer,
    setCurrentAnswer,
    progress,
    isFirstStep,
    isLastStep,
    handleNext,
    handleBack,
  } = useOnboardingState({ onComplete });

  return (
    <Dialog open={isOpen}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{currentQuestion?.title}</DialogTitle>
          <DialogDescription>
            Help us personalize your experience
          </DialogDescription>
        </DialogHeader>

        <div className="my-6">
          <Progress value={progress} className="mb-4" />

          {currentQuestion?.type === 'text' ? (
            <TextInput
              value={currentAnswer}
              onChange={setCurrentAnswer}
              placeholder={currentQuestion.placeholder}
            />
          ) : (
            <OptionCards
              options={currentQuestion?.options || []}
              value={currentAnswer}
              onChange={setCurrentAnswer}
            />
          )}
        </div>

        <DialogFooter>
          {!isFirstStep && (
            <Button
              variant="outline"
              onClick={handleBack}
            >
              Back
            </Button>
          )}
          <Button
            onClick={handleNext}
            disabled={!currentAnswer}
          >
            {isLastStep ? 'Complete' : 'Next'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default OnboardingFlow;

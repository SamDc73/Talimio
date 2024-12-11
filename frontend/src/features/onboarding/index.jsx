import React, { useState } from "react";

import { OptionCards } from "./OptionCards";
import { TextInput } from "./TextInput";
import { useOnboarding } from "./useOnboarding";

import { Button } from "@/components/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/dialog";
import { Progress } from "@/components/progress";
import { useToast } from "@/hooks/use-toast";

export const OnboardingFlow = ({ isOpen, onComplete }) => {
  const { topic, setTopic, getQuestions } = useOnboarding();
  const [step, setStep] = useState(0);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const handleTopicSubmit = async () => {
    if (!topic) return;
    setIsLoading(true);
    try {
      const fetchedQuestions = await getQuestions(topic);
      if (fetchedQuestions && fetchedQuestions.length > 0) {
        setQuestions(fetchedQuestions);
        setStep(1);
      }
    } catch (error) {
      console.error("Error fetching questions:", error);
      toast({
        title: "Error",
        description: "Failed to fetch questions. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnswerSelect = (question, answer) => {
    setAnswers((prev) => ({
      ...prev,
      [question]: answer,
    }));
  };

  const handleComplete = async () => {
    if (isLoading) return;

    setIsLoading(true);
    try {
      const skillLevel = answers[currentQuestion?.question]?.toLowerCase();
      const mappedSkillLevel =
        skillLevel === "advanced" ? "advanced" : skillLevel === "intermediate" ? "intermediate" : "beginner";

      const finalAnswers = {
        topic,
        skill_level: mappedSkillLevel,
        answers,
      };

      await onComplete(finalAnswers);
    } catch (error) {
      console.error("Error completing onboarding:", error);
      toast({
        title: "Error",
        description: "Failed to complete onboarding. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const currentQuestion = questions[step - 1];
  const progress = step === 0 ? 33 : (step / questions.length) * 66 + 33;

  // Prevent dialog from closing while loading
  const preventClose = isLoading ? true : undefined;

  return (
    <Dialog open={isOpen} onOpenChange={preventClose ? undefined : onComplete}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{step === 0 ? "What would you like to learn?" : currentQuestion?.question}</DialogTitle>
          <DialogDescription>Help us personalize your learning journey</DialogDescription>
        </DialogHeader>

        <div className="my-6">
          <Progress value={progress} className="mb-4" />

          {step === 0 ? (
            <TextInput value={topic} onChange={setTopic} placeholder="Enter a topic (e.g., machine learning)" />
          ) : (
            <OptionCards
              options={currentQuestion?.options || []}
              value={answers[currentQuestion?.question]}
              onChange={(answer) => handleAnswerSelect(currentQuestion?.question, answer)}
            />
          )}
        </div>

        <DialogFooter>
          {step > 0 && (
            <Button variant="outline" onClick={() => setStep((prev) => prev - 1)} disabled={isLoading}>
              Back
            </Button>
          )}
          <Button
            onClick={
              step === 0
                ? handleTopicSubmit
                : step === questions.length
                ? handleComplete
                : () => setStep((prev) => prev + 1)
            }
            disabled={isLoading || (step === 0 ? !topic : !answers[currentQuestion?.question])}
          >
            {isLoading ? "Loading..." : step === questions.length ? "Complete" : "Next"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

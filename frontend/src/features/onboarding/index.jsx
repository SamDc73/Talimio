import React, { useState } from "react";
import { Progress } from "@/components/progress";
import { Button } from "@/components/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/dialog";
import { TextInput } from "./TextInput";
import { OptionCards } from "./OptionCards";
import { useOnboarding } from "./useOnboarding";

export const OnboardingFlow = ({ isOpen, onComplete }) => {
  const { topic, setTopic, getQuestions, submitOnboarding } = useOnboarding();
  const [step, setStep] = useState(0);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [isLoading, setIsLoading] = useState(false);

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
    const finalAnswers = {
      topic,
      answers,
    };
    await submitOnboarding(finalAnswers);
    onComplete(finalAnswers);
  };

  const currentQuestion = questions[step - 1];
  const progress = step === 0 ? 33 : (step / questions.length) * 66 + 33;

  return (
    <Dialog open={isOpen}>
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
            <Button variant="outline" onClick={() => setStep((prev) => prev - 1)}>
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

export default OnboardingFlow;

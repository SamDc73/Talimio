import { useEffect, useState } from "react";

import { useOnboarding } from "./useOnboarding";

export const useOnboardingState = ({ onComplete, topic }) => {
  const { submitOnboarding, getOnboardingQuestions, questions: initialQuestions } = useOnboarding();
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [questions, setQuestions] = useState(initialQuestions || []);

  useEffect(() => {
    const fetchQuestions = async () => {
      if (topic) {
        const fetchedQuestions = await getOnboardingQuestions(topic);
        setQuestions(fetchedQuestions);
      }
    };
    fetchQuestions();
  }, [topic, getOnboardingQuestions]);

  const progress = ((currentStep + 1) / questions.length) * 100;
  const currentQuestion = questions[currentStep];
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === questions.length - 1;

  const handleNext = async () => {
    if (!currentAnswer) return;

    const updatedAnswers = {
      ...answers,
      [currentQuestion.id]: currentAnswer,
    };

    if (isLastStep) {
      try {
        const result = await submitOnboarding(updatedAnswers);
        onComplete(result);
      } catch (error) {
        console.error("Onboarding failed:", error);
      }
    } else {
      setAnswers(updatedAnswers);
      setCurrentStep((prev) => prev + 1);
      setCurrentAnswer("");
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => prev - 1);
    setCurrentAnswer(answers[questions[currentStep - 1].id] || "");
  };

  return {
    currentQuestion,
    currentAnswer,
    setCurrentAnswer,
    progress,
    isFirstStep,
    isLastStep,
    handleNext,
    handleBack,
  };
};

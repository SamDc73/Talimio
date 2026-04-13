import { useEffect, useMemo, useState } from "react"
import { QuizMarkdown } from "@/components/quiz/QuizMarkdown"
import {
	QUIZ_ACTIVE_BUTTON_CLASS_NAME,
	QUIZ_DISABLED_BUTTON_CLASS_NAME,
	QUIZ_ERROR_PANEL_CLASS_NAME,
	QUIZ_RESET_BUTTON_CLASS_NAME,
	QUIZ_SUCCESS_PANEL_CLASS_NAME,
	QUIZ_WIDGET_CLASS_NAME,
} from "@/components/quiz/quizUiClassNames"
import { cn } from "@/lib/utils"

export function MultipleChoice({
	question,
	options,
	correctAnswer,
	explanation,
	onSelect,
	selectedIndex,
	submitLabel = "Submit Answer",
}) {
	const isSurveyMode = typeof correctAnswer !== "number"

	const isControlled = typeof selectedIndex === "number" || selectedIndex === null
	const [internalSelected, setInternalSelected] = useState(selectedIndex ?? null)
	const [showFeedback, setShowFeedback] = useState(false)

	useEffect(() => {
		if (!isControlled) {
			return
		}
		setInternalSelected(selectedIndex ?? null)
	}, [isControlled, selectedIndex])

	useEffect(() => {
		if (isSurveyMode && showFeedback) {
			setShowFeedback(false)
		}
	}, [isSurveyMode, showFeedback])

	const effectiveSelected = isControlled ? (selectedIndex ?? null) : internalSelected
	const handleOptionChange = (index) => {
		if (!isSurveyMode && showFeedback) {
			return
		}

		if (!isControlled) {
			setInternalSelected(index)
		}

		onSelect?.(index)
	}

	const handleSubmit = () => {
		if (effectiveSelected !== null) {
			setShowFeedback(true)
		}
	}

	const handleReset = () => {
		if (!isControlled) {
			setInternalSelected(null)
		}
		setShowFeedback(false)
		onSelect?.(null)
	}

	const hasFeedback = !isSurveyMode && showFeedback
	const isCorrect = useMemo(() => {
		if (isSurveyMode || effectiveSelected === null) {
			return false
		}
		return effectiveSelected === correctAnswer
	}, [correctAnswer, effectiveSelected, isSurveyMode])
	const renderFeedbackSection = () => (
		<div>
			{explanation && (
				<div className={cn(isCorrect ? QUIZ_SUCCESS_PANEL_CLASS_NAME : QUIZ_ERROR_PANEL_CLASS_NAME, "mb-4 p-4")}>
					<div className={`text-sm font-medium mb-2 ${isCorrect ? "text-completed" : "text-destructive"}`}>
						{isCorrect ? "✓ Correct" : "✗ Incorrect"}
					</div>
					<QuizMarkdown content={explanation} className="text-sm/relaxed  text-muted-foreground [&_p]:m-0" />
				</div>
			)}
			<button type="button" onClick={handleReset} className={QUIZ_RESET_BUTTON_CLASS_NAME}>
				Try Again
			</button>
		</div>
	)
	const renderSubmitSection = () => (
		<button
			type="button"
			onClick={handleSubmit}
			disabled={effectiveSelected === null}
			className={effectiveSelected === null ? QUIZ_DISABLED_BUTTON_CLASS_NAME : QUIZ_ACTIVE_BUTTON_CLASS_NAME}
		>
			{submitLabel}
		</button>
	)

	return (
		<div className={QUIZ_WIDGET_CLASS_NAME} data-askai-exclude="true">
			<QuizMarkdown content={question} className="mb-6 text-lg font-medium text-foreground [&_p]:m-0" />

			<div className="mb-6 space-y-2">
				{options.map((option, index) => {
					const isCorrectOption = !isSurveyMode && index === correctAnswer
					const isSelected = index === effectiveSelected

					let optionClasses = "bg-background border border-border hover:bg-muted/30"

					if (hasFeedback) {
						if (isCorrectOption) {
							optionClasses =
								"bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
						} else if (isSelected) {
							optionClasses =
								"bg-destructive/10 border-destructive text-destructive dark:bg-destructive/20 dark:border-destructive/30 dark:text-destructive"
						} else {
							optionClasses = "bg-muted/20 border-border text-muted-foreground"
						}
					} else if (isSelected) {
						optionClasses = "bg-due-today/10 border-due-today/30 text-foreground"
					}

					return (
						<label
							key={`option-${index}-${option.slice(0, 10)}`}
							className={`flex items-start gap-3 p-4 rounded-lg transition-all cursor-pointer ${optionClasses} ${
								hasFeedback ? "cursor-default" : ""
							}`}
						>
							<input
								type="radio"
								name={`quiz-${question}`}
								value={index}
								checked={isSelected}
								onChange={() => handleOptionChange(index)}
								disabled={hasFeedback}
								className="mt-1 text-primary focus:ring-ring focus:ring-2 focus:ring-offset-0 border-input"
							/>
							<QuizMarkdown content={option} className="flex-1 text-sm/relaxed  [&_p]:m-0" />
							{hasFeedback && isCorrectOption && (
								<span className="text-completed dark:text-completed text-sm font-medium ml-2">✓</span>
							)}
						</label>
					)
				})}
			</div>

			{!isSurveyMode && (hasFeedback ? renderFeedbackSection() : renderSubmitSection())}
		</div>
	)
}

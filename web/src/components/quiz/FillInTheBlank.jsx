import { useState } from "react"
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

const INLINE_BLANK_PATTERN = /_{3,}/

function normalizeAnswer(value, caseSensitive) {
	const trimmedValue = value.trim()
	if (caseSensitive) {
		return trimmedValue
	}
	return trimmedValue.toLowerCase()
}

function hasSingleInlineBlank(question) {
	return question.split(INLINE_BLANK_PATTERN).length === 2
}

function InlineBlankQuestion({ isCorrect, question, selectedAnswer, showFeedback }) {
	const [beforeBlank, afterBlank] = question.split(INLINE_BLANK_PATTERN)
	const hasSelection = selectedAnswer.trim().length > 0

	let blankClassName =
		"mx-1 inline-flex min-h-11 min-w-32 items-center justify-center rounded-full border px-4 text-base font-medium transition-colors"
	if (!hasSelection) {
		blankClassName = `${blankClassName} border-dashed border-border text-muted-foreground`
	} else if (!showFeedback) {
		blankClassName = `${blankClassName} border-border bg-muted/20 text-foreground`
	} else if (isCorrect) {
		blankClassName = `${blankClassName} border-completed/30 bg-completed/10 text-completed`
	} else {
		blankClassName = `${blankClassName} border-destructive/30 bg-destructive/10 text-destructive`
	}

	return (
		<div className="mb-6 text-lg/relaxed font-medium text-foreground">
			<span>{beforeBlank}</span>
			<span className={blankClassName}>{hasSelection ? selectedAnswer : "Choose answer"}</span>
			<span>{afterBlank}</span>
		</div>
	)
}

export function FillInTheBlank({ question, answer, caseSensitive = false, explanation, options = [] }) {
	const [userAnswer, setUserAnswer] = useState("")
	const [showFeedback, setShowFeedback] = useState(false)
	const supportsChoiceMode = options.length >= 2 && hasSingleInlineBlank(question)

	const handleSubmit = () => {
		if (userAnswer.trim()) {
			setShowFeedback(true)
		}
	}

	const handleReset = () => {
		setUserAnswer("")
		setShowFeedback(false)
	}

	const isCorrect = normalizeAnswer(userAnswer, caseSensitive) === normalizeAnswer(answer, caseSensitive)

	let inputStateClass = "bg-background border-input placeholder:text-muted-foreground/70 focus:border-ring"
	if (showFeedback) {
		inputStateClass = isCorrect
			? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
			: "bg-destructive/10 border-destructive/30 text-destructive dark:bg-destructive/20 dark:border-destructive/30 dark:text-destructive"
	}

	return (
		<div className={QUIZ_WIDGET_CLASS_NAME} data-askai-exclude="true">
			{supportsChoiceMode ? (
				<>
					<InlineBlankQuestion
						isCorrect={isCorrect}
						question={question}
						selectedAnswer={userAnswer}
						showFeedback={showFeedback}
					/>

					<div className="mb-6 flex flex-wrap gap-2">
						{options.map((option) => {
							const isSelected = normalizeAnswer(option, caseSensitive) === normalizeAnswer(userAnswer, caseSensitive)
							const isCorrectOption = normalizeAnswer(option, caseSensitive) === normalizeAnswer(answer, caseSensitive)

							let optionClassName =
								"rounded-full border px-4 py-2 text-sm font-medium transition-colors disabled:cursor-default"
							if (showFeedback && isCorrectOption) {
								optionClassName = `${optionClassName} border-completed/30 bg-completed/10 text-completed`
							} else if (showFeedback && isSelected) {
								optionClassName = `${optionClassName} border-destructive/30 bg-destructive/10 text-destructive`
							} else if (isSelected) {
								optionClassName = `${optionClassName} border-primary/30 bg-primary/10 text-foreground`
							} else {
								optionClassName = `${optionClassName} border-border bg-background text-muted-foreground hover:bg-muted/30 hover:text-foreground`
							}

							return (
								<button
									key={option}
									type="button"
									onClick={() => !showFeedback && setUserAnswer(option)}
									disabled={showFeedback}
									className={optionClassName}
								>
									{option}
								</button>
							)
						})}
					</div>
				</>
			) : (
				<>
					<QuizMarkdown content={question} className="mb-6 text-lg font-medium text-foreground [&_p]:m-0" />

					<div className="mb-6">
						<input
							type="text"
							value={userAnswer}
							onChange={(e) => !showFeedback && setUserAnswer(e.target.value)}
							onKeyPress={(e) => {
								if (e.key === "Enter" && !showFeedback && userAnswer.trim()) {
									handleSubmit()
								}
							}}
							disabled={showFeedback}
							placeholder="Type your answer here..."
							className={`w-full px-4 py-3 text-sm rounded-lg border transition-all focus:ring-2 focus:ring-ring focus:outline-none ${inputStateClass}`}
						/>
					</div>
				</>
			)}

			{showFeedback ? (
				<div>
					<div className={cn(isCorrect ? QUIZ_SUCCESS_PANEL_CLASS_NAME : QUIZ_ERROR_PANEL_CLASS_NAME, "mb-4 p-4")}>
						<div className={`text-sm font-medium mb-2 ${isCorrect ? "text-completed" : "text-destructive"}`}>
							{isCorrect ? "✓ Correct" : "✗ Incorrect"}
						</div>
						{!isCorrect && (
							<p className="mb-2 text-sm text-muted-foreground">
								The correct answer is: <span className="font-medium text-foreground">{answer}</span>
							</p>
						)}
						{explanation && (
							<QuizMarkdown content={explanation} className="text-sm/relaxed  text-muted-foreground [&_p]:m-0" />
						)}
					</div>
					<button type="button" onClick={handleReset} className={QUIZ_RESET_BUTTON_CLASS_NAME}>
						Try Again
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={!userAnswer.trim()}
					className={userAnswer.trim() ? QUIZ_ACTIVE_BUTTON_CLASS_NAME : QUIZ_DISABLED_BUTTON_CLASS_NAME}
				>
					{supportsChoiceMode ? "Check Answer" : "Submit Answer"}
				</button>
			)}
		</div>
	)
}

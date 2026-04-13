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

export function FillInTheBlank({ question, answer, caseSensitive = false, explanation }) {
	const [userAnswer, setUserAnswer] = useState("")
	const [showFeedback, setShowFeedback] = useState(false)

	const handleSubmit = () => {
		if (userAnswer.trim()) {
			setShowFeedback(true)
		}
	}

	const handleReset = () => {
		setUserAnswer("")
		setShowFeedback(false)
	}

	const isCorrect = caseSensitive
		? userAnswer.trim() === answer
		: userAnswer.trim().toLowerCase() === answer.toLowerCase()
	let inputStateClass = "bg-background border-input placeholder:text-muted-foreground/70 focus:border-ring"
	if (showFeedback) {
		inputStateClass = isCorrect
			? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
			: "bg-destructive/10 border-destructive/30 text-destructive dark:bg-destructive/20 dark:border-destructive/30 dark:text-destructive"
	}

	return (
		<div className={QUIZ_WIDGET_CLASS_NAME} data-askai-exclude="true">
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
					Submit Answer
				</button>
			)}
		</div>
	)
}

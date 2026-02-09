import { useState } from "react"
import { QuizMarkdown } from "@/components/quiz/QuizMarkdown"

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
	let inputStateClass = "bg-background border-input focus:border-completed/40 placeholder:text-muted-foreground/70"
	if (showFeedback) {
		inputStateClass = isCorrect
			? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
			: "bg-destructive/10 border-destructive text-destructive dark:bg-destructive/20 dark:border-destructive/30 dark:text-destructive"
	}

	return (
		<div className="border-l-4 border-l-completed/20 pl-6 my-8 bg-background/30 rounded-r-lg" data-askai-exclude="true">
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
					<div className="p-4 mb-4 rounded-lg border border-border bg-muted/20">
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
					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-muted text-foreground hover:bg-muted/80 rounded-lg text-sm font-medium transition-colors"
					>
						Try Again
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={!userAnswer.trim()}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						userAnswer.trim()
							? "bg-completed text-completed-text hover:bg-completed/90"
							: "bg-muted text-muted-foreground cursor-not-allowed"
					}`}
				>
					Submit Answer
				</button>
			)}
		</div>
	)
}

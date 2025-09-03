import { useState } from "react"

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

	return (
		<div className="border-l-4 border-l-primary/20 pl-6 my-8 bg-card/30 rounded-r-lg">
			<h4 className="mb-6 text-lg font-medium text-foreground">{question}</h4>

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
					className={`w-full px-4 py-3 text-sm rounded-lg border transition-all focus:ring-2 focus:ring-primary/20 focus:outline-none ${
						showFeedback
							? isCorrect
								? "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-900/20 dark:border-emerald-800 dark:text-emerald-100"
								: "bg-red-50 border-red-200 text-red-900 dark:bg-red-900/20 dark:border-red-800 dark:text-red-100"
							: "bg-background border-border focus:border-primary/50 placeholder:text-muted-foreground"
					}`}
				/>
			</div>

			{!showFeedback ? (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={!userAnswer.trim()}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						!userAnswer.trim()
							? "bg-muted text-muted-foreground cursor-not-allowed"
							: "bg-primary text-primary-foreground hover:bg-primary/90"
					}`}
				>
					Submit Answer
				</button>
			) : (
				<div>
					<div className="p-4 mb-4 rounded-lg border border-border bg-muted/20">
						<div
							className={`text-sm font-medium mb-2 ${
								isCorrect ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300"
							}`}
						>
							{isCorrect ? "✓ Correct" : "✗ Incorrect"}
						</div>
						{!isCorrect && (
							<p className="mb-2 text-sm text-muted-foreground">
								The correct answer is: <span className="font-medium text-foreground">{answer}</span>
							</p>
						)}
						{explanation && <p className="text-sm leading-relaxed text-muted-foreground">{explanation}</p>}
					</div>
					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-lg text-sm font-medium transition-colors"
					>
						Try Again
					</button>
				</div>
			)}
		</div>
	)
}

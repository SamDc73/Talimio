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
		<div className="border-l-4 border-l-green-500/20 pl-6 my-8 bg-white/30 rounded-r-lg">
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
							: "bg-white border-gray-200 focus:border-green-500/50 placeholder:text-gray-400"
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
							? "bg-gray-100 text-gray-100-foreground cursor-not-allowed"
							: "bg-green-500 text-white hover:bg-green-500/90"
					}`}
				>
					Submit Answer
				</button>
			) : (
				<div>
					<div className="p-4 mb-4 rounded-lg border border-gray-200 bg-gray-100/20">
						<div
							className={`text-sm font-medium mb-2 ${
								isCorrect ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300"
							}`}
						>
							{isCorrect ? "✓ Correct" : "✗ Incorrect"}
						</div>
						{!isCorrect && (
							<p className="mb-2 text-sm text-gray-100-foreground">
								The correct answer is: <span className="font-medium text-foreground">{answer}</span>
							</p>
						)}
						{explanation && <p className="text-sm leading-relaxed text-gray-100-foreground">{explanation}</p>}
					</div>
					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-gray-100 text-foreground hover:bg-muted/80 rounded-lg text-sm font-medium transition-colors"
					>
						Try Again
					</button>
				</div>
			)}
		</div>
	)
}

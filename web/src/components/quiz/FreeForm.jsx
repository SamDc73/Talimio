import { useState } from "react"

export function FreeForm({ question, sampleAnswer, minLength = 50 }) {
	const [userAnswer, setUserAnswer] = useState("")
	const [submitted, setSubmitted] = useState(false)

	const handleSubmit = () => {
		if (userAnswer.length >= minLength) {
			setSubmitted(true)
		}
	}

	const handleReset = () => {
		setUserAnswer("")
		setSubmitted(false)
	}

	const remainingChars = Math.max(0, minLength - userAnswer.length)

	return (
		<div className="border-l-4 border-l-primary/20 pl-6 my-8 bg-card/30 rounded-r-lg">
			<h4 className="mb-6 text-lg font-medium text-foreground">{question}</h4>

			<div className="mb-6">
				<textarea
					value={userAnswer}
					onChange={(e) => !submitted && setUserAnswer(e.target.value)}
					disabled={submitted}
					placeholder="Type your answer here..."
					rows={4}
					className={`w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-primary/20 focus:outline-none placeholder:text-muted-foreground ${
						submitted
							? "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-900/20 dark:border-emerald-800 dark:text-emerald-100"
							: "bg-background border-border focus:border-primary/50"
					}`}
				/>
				{!submitted && (
					<div className="mt-2 text-xs text-muted-foreground">
						{remainingChars > 0 ? (
							<span className="text-amber-600 dark:text-amber-400">
								Please write at least {remainingChars} more characters
							</span>
						) : (
							<span className="text-emerald-600 dark:text-emerald-400">
								✓ Minimum length reached ({userAnswer.length} characters)
							</span>
						)}
					</div>
				)}
			</div>

			{!submitted ? (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={userAnswer.length < minLength}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						userAnswer.length < minLength
							? "bg-muted text-muted-foreground cursor-not-allowed"
							: "bg-primary text-primary-foreground hover:bg-primary/90"
					}`}
				>
					Submit Answer
				</button>
			) : (
				<div>
					<div className="p-4 mb-4 rounded-lg border border-border bg-muted/20">
						<div className="text-sm font-medium mb-2 text-emerald-700 dark:text-emerald-300">✓ Answer Submitted</div>
						<p className="text-sm leading-relaxed text-muted-foreground">
							Thank you for your thoughtful response. This is a free-form question, so there's no single correct answer.
						</p>
					</div>

					{sampleAnswer && (
						<details className="mb-4 group">
							<summary className="cursor-pointer p-4 rounded-lg border border-border bg-background hover:bg-muted/30 transition-colors">
								<span className="text-sm font-medium text-foreground group-open:text-primary">View Sample Answer</span>
							</summary>
							<div className="mt-3 p-4 rounded-lg bg-muted/20 border border-border">
								<p className="text-sm leading-relaxed text-muted-foreground">{sampleAnswer}</p>
							</div>
						</details>
					)}

					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-lg text-sm font-medium transition-colors"
					>
						Write Another Answer
					</button>
				</div>
			)}
		</div>
	)
}

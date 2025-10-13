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
		<div className="border-l-4 border-l-green-500/20 pl-6 my-8 bg-white/30 rounded-r-lg">
			<h4 className="mb-6 text-lg font-medium text-foreground">{question}</h4>

			<div className="mb-6">
				<textarea
					value={userAnswer}
					onChange={(e) => !submitted && setUserAnswer(e.target.value)}
					disabled={submitted}
					placeholder="Type your answer here..."
					rows={4}
					className={`w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-primary/20 focus:outline-none placeholder:text-gray-400 ${
						submitted
							? "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-900/20 dark:border-emerald-800 dark:text-emerald-100"
							: "bg-white border-gray-200 focus:border-green-500/50"
					}`}
				/>
				{!submitted && (
					<div className="mt-2 text-xs text-gray-100-foreground">
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
							? "bg-gray-100 text-gray-100-foreground cursor-not-allowed"
							: "bg-green-500 text-white hover:bg-green-500/90"
					}`}
				>
					Submit Answer
				</button>
			) : (
				<div>
					<div className="p-4 mb-4 rounded-lg border border-gray-200 bg-gray-100/20">
						<div className="text-sm font-medium mb-2 text-emerald-700 dark:text-emerald-300">✓ Answer Submitted</div>
						<p className="text-sm leading-relaxed text-gray-100-foreground">
							Thank you for your thoughtful response. This is a free-form question, so there's no single correct answer.
						</p>
					</div>

					{sampleAnswer && (
						<details className="mb-4 group">
							<summary className="cursor-pointer p-4 rounded-lg border border-gray-200 bg-white hover:bg-muted/30 transition-colors">
								<span className="text-sm font-medium text-foreground group-open:text-green-500">
									View Sample Answer
								</span>
							</summary>
							<div className="mt-3 p-4 rounded-lg bg-gray-100/20 border border-gray-200">
								<p className="text-sm leading-relaxed text-gray-100-foreground">{sampleAnswer}</p>
							</div>
						</details>
					)}

					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-gray-100 text-foreground hover:bg-gray-100/80 rounded-lg text-sm font-medium transition-colors"
					>
						Write Another Answer
					</button>
				</div>
			)}
		</div>
	)
}

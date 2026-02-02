import { useState } from "react"
import { QuizMarkdown } from "@/components/quiz/QuizMarkdown.jsx"

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
		<div className="border-l-4 border-l-completed/20 pl-6 my-8 bg-background/30 rounded-r-lg" data-askai-exclude="true">
			<QuizMarkdown content={question} className="mb-6 text-lg font-medium text-foreground [&_p]:m-0" />

			<div className="mb-6">
				<textarea
					value={userAnswer}
					onChange={(e) => !submitted && setUserAnswer(e.target.value)}
					disabled={submitted}
					placeholder="Type your answer here..."
					rows={4}
					className={`w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 ${
						submitted
							? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
							: "bg-background border-input focus:border-completed/40"
					}`}
				/>
				{!submitted && (
					<div className="mt-2 text-xs text-muted-foreground">
						{remainingChars > 0 ? (
							<span className="text-due-today">Please write at least {remainingChars} more characters</span>
						) : (
							<span className="text-completed">✓ Minimum length reached ({userAnswer.length} characters)</span>
						)}
					</div>
				)}
			</div>

			{submitted ? (
				<div>
					<div className="p-4 mb-4 rounded-lg border border-border bg-muted/20">
						<div className="text-sm font-medium mb-2 text-completed">✓ Answer Submitted</div>

						<p className="text-sm/relaxed  text-muted-foreground">
							Thank you for your thoughtful response. This is a free-form question, so there's no single correct answer.
						</p>
					</div>

					{sampleAnswer && (
						<details className="mb-4 group">
							<summary className="cursor-pointer p-4 rounded-lg border border-border bg-background hover:bg-muted/30 transition-colors">
								<span className="text-sm font-medium text-foreground group-open:text-primary">View Sample Answer</span>
							</summary>
							<div className="mt-3 p-4 rounded-lg bg-muted/20 border border-border">
								<QuizMarkdown content={sampleAnswer} className="text-sm/relaxed  text-muted-foreground [&_p]:m-0" />
							</div>
						</details>
					)}

					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-muted text-foreground hover:bg-muted/80 rounded-lg text-sm font-medium transition-colors"
					>
						Write Another Answer
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={userAnswer.length < minLength}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						userAnswer.length < minLength
							? "bg-muted text-muted-foreground cursor-not-allowed"
							: "bg-completed text-completed-text hover:bg-completed/90"
					}`}
				>
					Submit Answer
				</button>
			)}
		</div>
	)
}

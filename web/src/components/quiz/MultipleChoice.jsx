import { useState } from "react"

export function MultipleChoice({ question, options, correctAnswer, explanation }) {
	const [selectedAnswer, setSelectedAnswer] = useState(null)
	const [showFeedback, setShowFeedback] = useState(false)

	const handleSubmit = () => {
		if (selectedAnswer !== null) {
			setShowFeedback(true)
		}
	}

	const handleReset = () => {
		setSelectedAnswer(null)
		setShowFeedback(false)
	}

	const isCorrect = selectedAnswer === correctAnswer

	return (
		<div className="border-l-4 border-l-green-500/20 pl-6 my-8 bg-white/30 rounded-r-lg">
			<h4 className="mb-6 text-lg font-medium text-gray-900">{question}</h4>

			<div className="mb-6 space-y-2">
				{options.map((option, index) => {
					const isCorrectOption = index === correctAnswer
					const isSelected = index === selectedAnswer

					let optionClasses = "bg-white border border-gray-200 hover:bg-gray-100/30"

					if (showFeedback) {
						if (isCorrectOption) {
							optionClasses =
								"bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-900/20 dark:border-emerald-800 dark:text-emerald-100"
						} else if (isSelected) {
							optionClasses =
								"bg-red-50 border-red-200 text-red-900 dark:bg-red-900/20 dark:border-red-800 dark:text-red-100"
						} else {
							optionClasses = "bg-gray-100/20 border-gray-200 text-gray-100-foreground"
						}
					} else if (isSelected) {
						optionClasses = "bg-green-500/5 border-green-500/30 text-gray-900"
					}

					return (
						<label
							key={`option-${index}-${option.slice(0, 10)}`}
							className={`flex items-start gap-3 p-4 rounded-lg transition-all cursor-pointer ${optionClasses} ${
								showFeedback ? "cursor-default" : ""
							}`}
						>
							<input
								type="radio"
								name={`quiz-${question}`}
								value={index}
								checked={selectedAnswer === index}
								onChange={() => !showFeedback && setSelectedAnswer(index)}
								disabled={showFeedback}
								className="mt-1 text-green-500 focus:ring-green-500 focus:ring-2 focus:ring-offset-0 border-gray-400"
							/>
							<span className="flex-1 text-sm leading-relaxed">{option}</span>
							{showFeedback && isCorrectOption && (
								<span className="text-emerald-700 dark:text-emerald-300 text-sm font-medium ml-2">✓</span>
							)}
						</label>
					)
				})}
			</div>

			{!showFeedback ? (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={selectedAnswer === null}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						selectedAnswer === null
							? "bg-gray-100 text-gray-100-foreground cursor-not-allowed"
							: "bg-green-500 text-white hover:bg-green-500/90"
					}`}
				>
					Submit Answer
				</button>
			) : (
				<div>
					{explanation && (
						<div className="p-4 mb-4 rounded-lg border border-gray-200 bg-gray-100/20">
							<div
								className={`text-sm font-medium mb-2 ${
									isCorrect ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300"
								}`}
							>
								{isCorrect ? "✓ Correct" : "✗ Incorrect"}
							</div>
							<p className="text-sm leading-relaxed text-gray-100-foreground">{explanation}</p>
						</div>
					)}
					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-gray-100 text-gray-900 hover:bg-gray-100/80 rounded-lg text-sm font-medium transition-colors"
					>
						Try Again
					</button>
				</div>
			)}
		</div>
	)
}

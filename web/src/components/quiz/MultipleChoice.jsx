import { useEffect, useMemo, useState } from "react"

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

	return (
		<div className="border-l-4 border-l-completed/20 pl-6 my-8 bg-background/30 rounded-r-lg" data-askai-exclude="true">
			<h4 className="mb-6 text-lg font-medium text-foreground">{question}</h4>

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
						optionClasses = "bg-completed/10 border-completed/30 text-foreground"
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
							<span className="flex-1 text-sm leading-relaxed">{option}</span>
							{hasFeedback && isCorrectOption && (
								<span className="text-completed dark:text-completed text-sm font-medium ml-2">✓</span>
							)}
						</label>
					)
				})}
			</div>

			{!isSurveyMode ? (
				hasFeedback ? (
					<div>
						{explanation && (
							<div className="p-4 mb-4 rounded-lg border border-border bg-muted/20">
								<div className={`text-sm font-medium mb-2 ${isCorrect ? "text-completed" : "text-destructive"}`}>
									{isCorrect ? "✓ Correct" : "✗ Incorrect"}
								</div>
								<p className="text-sm leading-relaxed text-muted-foreground">{explanation}</p>
							</div>
						)}
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
						disabled={effectiveSelected === null}
						className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
							effectiveSelected === null
								? "bg-muted text-muted-foreground cursor-not-allowed"
								: "bg-completed text-completed-text hover:bg-completed/90"
						}`}
					>
						{submitLabel}
					</button>
				)
			) : null}
		</div>
	)
}

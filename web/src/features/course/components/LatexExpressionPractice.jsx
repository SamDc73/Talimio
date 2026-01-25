import { useCallback, useEffect, useId } from "react"
import { LatexExpression } from "@/components/quiz/LatexExpression.jsx"
import { usePracticeRegistry } from "../hooks/use-practice-registry.js"
import { useLatexPracticeReview } from "../hooks/useLatexPracticeReview.js"

export function LatexExpressionPractice({
	question,
	expectedLatex,
	criteria,
	hints,
	solutionLatex,
	solutionMdx,
	practiceContext = "inline",
	courseId,
	lessonId,
	lessonConceptId,
	conceptId,
	renderInQuickCheck = false,
	onComplete,
}) {
	const { registerItem, unregisterItem } = usePracticeRegistry()
	const itemId = useId()
	const resolvedConceptId = conceptId ?? lessonConceptId ?? null
	const shouldRegister = !renderInQuickCheck
	const shouldRenderInline = !(practiceContext === "quick_check" && !renderInQuickCheck)

	const { submitAnswer, submitSkip } = useLatexPracticeReview({
		courseId,
		lessonId,
		conceptId: resolvedConceptId,
		practiceContext,
	})

	useEffect(() => {
		if (!shouldRegister) {
			return
		}

		registerItem({
			id: itemId,
			question,
			expectedLatex,
			criteria,
			hints,
			solutionLatex,
			solutionMdx,
			practiceContext,
			conceptId: resolvedConceptId,
			courseId,
			lessonId,
		})

		return () => {
			unregisterItem(itemId)
		}
	}, [
		courseId,
		criteria,
		expectedLatex,
		hints,
		itemId,
		lessonId,
		practiceContext,
		question,
		registerItem,
		resolvedConceptId,
		shouldRegister,
		solutionLatex,
		solutionMdx,
		unregisterItem,
	])

	const handleGrade = useCallback(
		async (payload) => {
			return await submitAnswer({
				...payload,
				conceptId: resolvedConceptId,
				practiceContext,
			})
		},
		[practiceContext, resolvedConceptId, submitAnswer]
	)

	const handleSkip = useCallback(
		async (payload) => {
			return await submitSkip({
				...payload,
				conceptId: resolvedConceptId,
				practiceContext,
			})
		},
		[practiceContext, resolvedConceptId, submitSkip]
	)

	if (!shouldRenderInline) {
		return null
	}

	return (
		<LatexExpression
			question={question}
			expectedLatex={expectedLatex}
			criteria={criteria}
			hints={hints}
			solutionLatex={solutionLatex}
			solutionMdx={solutionMdx}
			practiceContext={practiceContext}
			onGrade={handleGrade}
			onSkip={handleSkip}
			onComplete={onComplete}
		/>
	)
}

export default LatexExpressionPractice

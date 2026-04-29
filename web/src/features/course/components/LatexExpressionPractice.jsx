import { useCallback, useEffect, useId } from "react"
import { LatexExpression } from "@/components/quiz/LatexExpression"
import { useLatexPracticeReview } from "../hooks/use-latex-practice-review"
import { usePracticeRegistry } from "../hooks/use-practice-registry"

export function LatexExpressionPractice({
	questionId,
	question,
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
			questionId,
			question,
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
		hints,
		itemId,
		lessonId,
		practiceContext,
		questionId,
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
				questionId,
				conceptId: resolvedConceptId,
				practiceContext,
			})
		},
		[practiceContext, questionId, resolvedConceptId, submitAnswer]
	)

	const handleSkip = useCallback(
		async (payload) => {
			return await submitSkip({
				...payload,
				questionId,
				conceptId: resolvedConceptId,
				practiceContext,
			})
		},
		[practiceContext, questionId, resolvedConceptId, submitSkip]
	)

	if (!shouldRenderInline) {
		return null
	}

	if (!questionId) {
		return (
			<div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
				This practice question is unavailable because it is missing its server-owned question ID.
			</div>
		)
	}

	return (
		<LatexExpression
			question={question}
			answerKind="latex"
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

// biome-ignore lint/style/useComponentExportOnlyModules: this file keeps the named and default component export together for existing MDX and lesson imports.
export default LatexExpressionPractice

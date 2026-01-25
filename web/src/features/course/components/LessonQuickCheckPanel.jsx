import { useCallback, useEffect, useMemo, useState } from "react"
import { Button } from "@/components/Button"
import { usePracticeItems } from "../hooks/use-practice-registry.js"
import { LatexExpressionPractice } from "./LatexExpressionPractice.jsx"

const DEFAULT_QUESTION_COUNT = 2

export function LessonQuickCheckPanel({ courseId, lessonId, lessonConceptId }) {
	const quickCheckItems = usePracticeItems({ practiceContext: "quick_check" })
	const [visibleCount, setVisibleCount] = useState(DEFAULT_QUESTION_COUNT)
	const [currentIndex, setCurrentIndex] = useState(0)
	const [completedIds, setCompletedIds] = useState([])
	const [isDismissed, setIsDismissed] = useState(false)

	const itemKey = useMemo(() => quickCheckItems.map((item) => item.id).join("|"), [quickCheckItems])

	useEffect(() => {
		if (!itemKey) {
			setVisibleCount(0)
			setCurrentIndex(0)
			setCompletedIds([])
			setIsDismissed(false)
			return
		}

		setVisibleCount(Math.min(DEFAULT_QUESTION_COUNT, quickCheckItems.length))
		setCurrentIndex(0)
		setCompletedIds([])
		setIsDismissed(false)
	}, [itemKey, quickCheckItems.length])

	const visibleItems = useMemo(() => quickCheckItems.slice(0, visibleCount), [quickCheckItems, visibleCount])
	const completedSet = useMemo(() => new Set(completedIds), [completedIds])

	useEffect(() => {
		if (visibleItems.length === 0) {
			return
		}
		setCurrentIndex((value) => {
			const next = Math.min(value, visibleItems.length - 1)
			return next === value ? value : next
		})
	}, [visibleItems.length])

	const currentItem = visibleItems[currentIndex] ?? null
	const totalVisible = visibleItems.length
	const completedCount = useMemo(() => {
		let count = 0
		for (const item of visibleItems) {
			if (completedSet.has(item.id)) {
				count += 1
			}
		}
		return count
	}, [completedSet, visibleItems])

	const allComplete = totalVisible > 0 && completedCount >= totalVisible
	const isCurrentComplete = currentItem ? completedSet.has(currentItem.id) : false

	const progressLabel = useMemo(() => {
		if (totalVisible === 0) {
			return null
		}
		if (allComplete) {
			return `${totalVisible}/${totalVisible}`
		}
		return `${Math.min(currentIndex + 1, totalVisible)}/${totalVisible}`
	}, [allComplete, currentIndex, totalVisible])

	const handleComplete = useCallback(() => {
		if (!currentItem) {
			return
		}
		setCompletedIds((prev) => {
			if (prev.includes(currentItem.id)) {
				return prev
			}
			return [...prev, currentItem.id]
		})
	}, [currentItem])

	const handleNext = useCallback(() => {
		if (!visibleItems.length) {
			return
		}
		let nextIndex = -1
		for (let i = currentIndex + 1; i < visibleItems.length; i += 1) {
			const item = visibleItems[i]
			if (!completedSet.has(item.id)) {
				nextIndex = i
				break
			}
		}
		if (nextIndex === -1) {
			return
		}
		setCurrentIndex((value) => (value === nextIndex ? value : nextIndex))
	}, [completedSet, currentIndex, visibleItems])

	const handlePracticeMore = useCallback(() => {
		const nextCount = Math.min(visibleCount + 1, quickCheckItems.length)
		if (nextCount === visibleCount) {
			return
		}
		setVisibleCount(nextCount)
		setCurrentIndex((value) => {
			const nextIndex = Math.min(nextCount - 1, quickCheckItems.length - 1)
			return value === nextIndex ? value : nextIndex
		})
	}, [quickCheckItems.length, visibleCount])

	if (isDismissed || quickCheckItems.length === 0) {
		return null
	}

	return (
		<section className="mt-8 rounded-xl border border-border/60 bg-background/60 shadow-sm">
			<div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 px-5 py-4">
				<div>
					<p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Quick Check</p>
					<p className="text-sm text-muted-foreground">Two-minute checkpoint before you move on.</p>
				</div>
				<div className="flex items-center gap-3">
					{progressLabel ? (
						<span className="rounded-full bg-muted/60 px-3 py-1 text-xs font-semibold text-muted-foreground">
							{progressLabel}
						</span>
					) : null}
					<Button type="button" variant="outline" size="sm" onClick={() => setIsDismissed(true)}>
						Done for now
					</Button>
				</div>
			</div>

			<div className="px-5 py-6">
				{allComplete ? (
					<div className="space-y-4">
						<p className="text-sm text-muted-foreground">Nice work — you finished this quick check.</p>
						<div className="flex flex-wrap items-center gap-3">
							{quickCheckItems.length > visibleCount ? (
								<Button type="button" size="sm" onClick={handlePracticeMore}>
									Practice more (+1)
								</Button>
							) : null}
							<Button type="button" variant="outline" size="sm" onClick={() => setIsDismissed(true)}>
								Done for now
							</Button>
						</div>
					</div>
				) : currentItem ? (
					<div className="space-y-4">
						<LatexExpressionPractice
							key={currentItem.id}
							question={currentItem.question}
							expectedLatex={currentItem.expectedLatex}
							criteria={currentItem.criteria}
							hints={currentItem.hints}
							solutionLatex={currentItem.solutionLatex}
							solutionMdx={currentItem.solutionMdx}
							practiceContext="quick_check"
							courseId={currentItem.courseId ?? courseId}
							lessonId={currentItem.lessonId ?? lessonId}
							lessonConceptId={currentItem.conceptId ?? lessonConceptId}
							renderInQuickCheck={true}
							onComplete={handleComplete}
						/>

						{isCurrentComplete ? (
							<div className="flex flex-wrap items-center gap-3">
								{visibleItems.length > 1 && !allComplete ? (
									<Button type="button" size="sm" onClick={handleNext}>
										Next question
									</Button>
								) : null}
								{allComplete ? (
									<Button type="button" size="sm" onClick={handlePracticeMore}>
										Practice more (+1)
									</Button>
								) : null}
							</div>
						) : null}
					</div>
				) : (
					<p className="text-sm text-muted-foreground">No quick check items available yet.</p>
				)}
			</div>
		</section>
	)
}

export default LessonQuickCheckPanel

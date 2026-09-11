import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Circle } from "lucide-react"
import { useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { fetchConceptFrontierByCourseId, fetchQuestionBankByCourseId } from "@/api/courseApi"
import { Button } from "@/components/Button"
import { MasteryCircle } from "@/components/MasteryCircle"
import { useCourseContext } from "@/features/course/CourseContext"

const CONCEPT_ROW_CLASS_NAME =
	"group flex items-center gap-3 rounded-2xl border border-transparent px-4 py-3 transition-colors hover:border-border hover:bg-muted/40 md:px-5 md:py-3.5"
const CONCEPT_ACTION_CLASS_NAME =
	"flex min-w-0 flex-1 items-center justify-between gap-3 rounded-xl px-2 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"

function questionCountLabel(count) {
	if (count === 0) {
		return "AI-generated"
	}
	return count === 1 ? "1 question" : `${count} questions`
}

function ConceptSection({ number, title, concepts, bankCountByConcept, onOpen, locked = false }) {
	if (concepts.length === 0) {
		return null
	}
	return (
		<div className="relative overflow-hidden rounded-3xl border border-border/70 bg-card/95 p-5 md:p-6 lg:p-7 shadow-sm">
			<div className="mb-5 flex w-full items-center gap-3 md:gap-4">
				<div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-border/70 bg-muted/60 text-sm font-medium text-muted-foreground">
					{number}
				</div>
				<h2 className="flex-1 truncate text-lg font-semibold text-foreground md:text-xl">{title}</h2>
			</div>
			<div className="space-y-2.5">
				{concepts.map((concept) => {
					const count = bankCountByConcept.get(String(concept.id)) ?? 0
					const mastery = typeof concept.mastery === "number" ? Math.round(concept.mastery * 100) : 0
					if (locked) {
						return (
							<div
								key={concept.id}
								className="flex items-center gap-3 rounded-2xl border border-transparent px-4 py-3 md:px-5 md:py-3.5 opacity-60"
							>
								<Circle className="size-5 shrink-0 text-muted-foreground/50" />
								<span className="truncate text-sm font-medium text-muted-foreground">{concept.name}</span>
								<span className="ml-auto shrink-0 text-xs text-muted-foreground">{questionCountLabel(count)}</span>
							</div>
						)
					}
					return (
						<div key={concept.id} className={CONCEPT_ROW_CLASS_NAME}>
							<MasteryCircle value={mastery} className="shrink-0 text-muted-foreground" />
							<button type="button" onClick={() => onOpen(concept.id)} className={CONCEPT_ACTION_CLASS_NAME}>
								<span className="truncate text-sm font-medium text-foreground">{concept.name}</span>
								<span className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
									{questionCountLabel(count)}
									<ArrowRight className="size-4 text-muted-foreground/60 opacity-0 transition-opacity group-hover:opacity-100" />
								</span>
							</button>
						</div>
					)
				})}
			</div>
		</div>
	)
}

/**
 * Landing page for a question-bank course: no lessons, only the concept graph the
 * instructor's questions were mapped onto, with practice as the single action.
 */
export default function QuestionBankView() {
	const { courseId, adaptiveProgressPct } = useCourseContext()
	const navigate = useNavigate()

	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: ({ signal }) => fetchConceptFrontierByCourseId(courseId, signal),
		enabled: Boolean(courseId),
		staleTime: 30_000,
		refetchOnWindowFocus: false,
	})
	const { data: bankData } = useQuery({
		queryKey: ["course", courseId, "question-bank"],
		queryFn: ({ signal }) => fetchQuestionBankByCourseId(courseId, signal),
		enabled: Boolean(courseId),
		staleTime: 60_000,
		refetchOnWindowFocus: false,
	})

	const bankCountByConcept = useMemo(() => {
		const counts = new Map()
		for (const question of bankData?.questions ?? []) {
			if (!question?.conceptId) continue
			const key = String(question.conceptId)
			counts.set(key, (counts.get(key) ?? 0) + 1)
		}
		return counts
	}, [bankData])

	const dueList = Array.isArray(frontierData?.dueForReview) ? frontierData.dueForReview : []
	const readyList = Array.isArray(frontierData?.frontier) ? frontierData.frontier : []
	const upcomingList = Array.isArray(frontierData?.comingSoon) ? frontierData.comingSoon : []
	const nextConcept = dueList[0] ?? readyList[0] ?? null
	const totalQuestions = bankData?.questions?.length ?? 0
	const masteryPct = typeof adaptiveProgressPct === "number" ? adaptiveProgressPct : 0

	const openFocusedPractice = (conceptId) => {
		navigate(`/course/${courseId}/practice?focusConceptId=${encodeURIComponent(String(conceptId))}`)
	}

	let sectionNumber = 0
	const nextNumber = () => {
		sectionNumber += 1
		return sectionNumber
	}

	return (
		<div className="flex-1 bg-background">
			<div className="mx-auto w-full max-w-container-4xl px-4 py-6 md:px-6 md:py-8 lg:px-8 lg:py-10">
				<div className="flex flex-col gap-6 md:gap-8 lg:gap-10">
					<section className="rounded-3xl border border-border/70 bg-card/95 shadow-sm ring-1 ring-border/40">
						<div className="flex flex-col gap-6 p-5 md:p-6 lg:p-7">
							<div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
								<div className="min-w-0 flex-1 space-y-2">
									<div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Next up
									</div>
									<h2 className="truncate text-lg/tight font-semibold text-foreground md:text-xl">
										{nextConcept ? nextConcept.name : "All caught up"}
									</h2>
									<p className="text-xs text-muted-foreground/80">
										{totalQuestions} questions from your instructor · Mastery {masteryPct}%
									</p>
								</div>
								<Button
									onClick={() => navigate(`/course/${courseId}/practice`)}
									variant="outline"
									className="h-9 rounded-full px-4"
								>
									<span className="text-sm font-semibold">Start practice</span>
									<ArrowRight className="size-4" />
								</Button>
							</div>
						</div>
					</section>

					<section className="flex flex-col gap-4 md:gap-5 lg:gap-6">
						<ConceptSection
							number={dueList.length > 0 ? nextNumber() : 0}
							title="Due for review"
							concepts={dueList}
							bankCountByConcept={bankCountByConcept}
							onOpen={openFocusedPractice}
						/>
						<ConceptSection
							number={readyList.length > 0 ? nextNumber() : 0}
							title="Ready to practice"
							concepts={readyList}
							bankCountByConcept={bankCountByConcept}
							onOpen={openFocusedPractice}
						/>
						<ConceptSection
							number={upcomingList.length > 0 ? nextNumber() : 0}
							title="Upcoming"
							concepts={upcomingList}
							bankCountByConcept={bankCountByConcept}
							onOpen={openFocusedPractice}
							locked
						/>
					</section>
				</div>
			</div>
		</div>
	)
}

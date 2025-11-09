import { AlertTriangle, Check, Zap } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/Button"
import logger from "@/lib/logger"
import { cn } from "@/lib/utils"
import { useAdaptiveSession } from "../hooks/useAdaptiveSession.js"
import { useLectorReview } from "../hooks/useLectorReview.js"

const RATING_OPTIONS = [
	{ value: 1, label: "Again", tone: "border-destructive/40 text-destructive" },
	{ value: 2, label: "Hard", tone: "border-amber-400/60 text-amber-600" },
	{ value: 3, label: "Good", tone: "border-emerald-400/50 text-emerald-600" },
	{ value: 4, label: "Easy", tone: "border-emerald-300/60 text-emerald-700" },
]

function formatIn(nextTs) {
	try {
		const t = typeof nextTs === "string" ? new Date(nextTs) : nextTs
		const diffMs = Math.max(0, t.getTime() - Date.now())
		const mins = Math.round(diffMs / 60000)
		if (mins < 60) return `in ${mins}m`
		const hours = Math.floor(mins / 60)
		const remM = mins % 60
		if (hours < 24) return remM > 0 ? `in ${hours}h ${remM}m` : `in ${hours}h`
		const days = Math.round(hours / 24)
		return `in ${days}d`
	} catch (_e) {
		return "soon"
	}
}

export function AdaptiveReviewPanel({
	courseId,
	lessonId,
	lessonConceptId,
	adaptiveEnabled: adaptiveEnabledProp = false,
	className,
}) {
	const { adaptive, persistAdaptiveMetadata, onReviewSuccess, onReviewError } = useAdaptiveSession(courseId, lessonId)
	const {
		submitReview,
		isSubmitting,
		error: submissionError,
	} = useLectorReview({
		courseId,
		lessonId,
		onSuccess: onReviewSuccess,
		onError: onReviewError,
	})
	const [hasLoggedPrompt, setHasLoggedPrompt] = useState(false)
	const [selectedRating, setSelectedRating] = useState(null)
	const [hasSubmitted, setHasSubmitted] = useState(false)
	const [nextReviewAt, setNextReviewAt] = useState(null)
	const promptStartRef = useRef(null)

	const derivedConcept = adaptive?.nextConcept ?? null
	const fallbackConcept = lessonConceptId
		? { conceptId: String(lessonConceptId), title: null, description: null }
		: null
	const activeConcept = derivedConcept ?? fallbackConcept

	const isAdaptiveActive = adaptive?.enabled || adaptiveEnabledProp
	const conceptId = activeConcept?.conceptId ?? null

	useEffect(() => {
		if (!isAdaptiveActive || !conceptId || hasLoggedPrompt) {
			return
		}

		setHasLoggedPrompt(true)

		persistAdaptiveMetadata?.({
			adaptive_state_update: {
				last_review_prompted_at: new Date().toISOString(),
				last_review_prompted_concept: conceptId,
			},
		}).catch((error) => {
			logger.error("Failed to persist adaptive prompt metadata", error, {
				courseId,
				lessonId,
				conceptId,
			})
		})
	}, [conceptId, courseId, hasLoggedPrompt, isAdaptiveActive, lessonId, persistAdaptiveMetadata])

	useEffect(() => {
		if (!conceptId) {
			setHasLoggedPrompt(false)
			setSelectedRating(null)
			setHasSubmitted(false)
			promptStartRef.current = null
			return
		}

		setHasSubmitted(false)
		setSelectedRating(null)
		promptStartRef.current = Date.now()
	}, [conceptId])

	if (!isAdaptiveActive || !conceptId) {
		return null
	}

	const handleRating = async (rating) => {
		setSelectedRating(rating)
		try {
			const start = typeof promptStartRef.current === "number" ? promptStartRef.current : Date.now() - 1000
			const duration = Math.max(500, Date.now() - start)
			const response = await submitReview({ conceptId, rating, reviewDurationMs: duration })
			const primaryOutcome = Array.isArray(response?.outcomes) ? response.outcomes[0] : null
			const ts = primaryOutcome?.nextReviewAt ?? primaryOutcome?.next_review_at ?? null
			setNextReviewAt(ts)
			setHasSubmitted(true)
		} catch (error) {
			setSelectedRating(null)
			logger.error("Adaptive review submission failed", error, {
				courseId,
				lessonId,
				conceptId,
			})
		}
	}

	return (
		<section className={cn("rounded-xl border border-border/60 bg-muted/40 backdrop-blur-sm", className)}>
			<div className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-4">
				<div>
					<p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
						Tell us how this concept felt
					</p>
				</div>
				<span className="flex items-center gap-1 rounded-full bg-[var(--color-course)]/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-course)]">
					<Zap className="h-3.5 w-3.5" aria-hidden="true" />
					Active
				</span>
			</div>

			<div className="space-y-4 px-5 py-6">
				<div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
					{RATING_OPTIONS.map((option) => (
						<Button
							key={option.value}
							type="button"
							onClick={() => handleRating(option.value)}
							disabled={isSubmitting || hasSubmitted}
							variant="outline"
							className={cn(
								"h-10 rounded-full border bg-background/70 text-sm font-medium transition",
								option.tone,
								selectedRating === option.value &&
									"bg-[var(--color-course)]/10 border-[var(--color-course)] text-[var(--color-course)]",
								(isSubmitting || hasSubmitted) && "opacity-60"
							)}
						>
							{option.label}
						</Button>
					))}
				</div>

				{submissionError ? (
					<div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
						<AlertTriangle className="mt-0.5 h-4 w-4" aria-hidden="true" />
						<p>We couldn&apos;t save that rating. Please try again.</p>
					</div>
				) : null}

				{hasSubmitted ? (
					<div className="flex items-center gap-2 rounded-lg border border-emerald-400/40 bg-emerald-50/60 px-4 py-3 text-sm text-emerald-700">
						<Check className="h-4 w-4" aria-hidden="true" />
						<p>
							Saved.
							{nextReviewAt ? (
								<span className="ml-1">Next review {formatIn(nextReviewAt)}.</span>
							) : (
								<span className="ml-1">We’ll remind you at the right time.</span>
							)}
						</p>
					</div>
				) : null}
			</div>
		</section>
	)
}

export default AdaptiveReviewPanel

import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { fetchCourseShare, forkCourseShare } from "@/api/courseApi"
import { Button } from "@/components/Button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/Card"
import logger from "@/lib/logger"

const MODE_LABELS = {
	question_bank: "Question bank",
	adaptive: "Adaptive course",
	standard: "Course",
}
const CONCEPT_PREVIEW_LIMIT = 8

function questionCountLabel(count) {
	return count === 1 ? "1 question" : `${count} questions`
}

/**
 * Landing page for a share link (/join/:token): shows what the shared course is,
 * then adds a fresh copy to the learner's library on confirmation.
 */
export default function JoinCourseView() {
	const { token } = useParams()
	const navigate = useNavigate()
	const [isAdding, setIsAdding] = useState(false)
	const [addError, setAddError] = useState("")

	const {
		data: preview,
		isLoading,
		error,
	} = useQuery({
		queryKey: ["course-share", token],
		queryFn: ({ signal }) => fetchCourseShare(token, signal),
		enabled: Boolean(token),
		retry: false,
	})

	const handleAdd = async () => {
		setIsAdding(true)
		setAddError("")
		try {
			const course = await forkCourseShare(token)
			navigate(`/course/${course.id}`, { replace: true })
		} catch (err) {
			logger.error("Failed to add shared course", { token, error: err })
			setAddError(err?.message || "Unable to add this course right now.")
			setIsAdding(false)
		}
	}

	let body = (
		<div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
			<Loader2 className="size-4 animate-spin" />
			Loading shared course...
		</div>
	)

	if (!isLoading && (error || !preview)) {
		body = (
			<Card className="w-full max-w-container-lg">
				<CardHeader>
					<CardTitle>This link isn't valid</CardTitle>
					<CardDescription>The share link may have been removed, or the course no longer exists.</CardDescription>
				</CardHeader>
				<CardFooter>
					<Button variant="outline" onClick={() => navigate("/")}>
						Back to my courses
					</Button>
				</CardFooter>
			</Card>
		)
	} else if (preview) {
		const conceptNames = Array.isArray(preview.conceptNames) ? preview.conceptNames : []
		const shownConcepts = conceptNames.slice(0, CONCEPT_PREVIEW_LIMIT)
		const hiddenConceptCount = conceptNames.length - shownConcepts.length

		body = (
			<Card className="w-full max-w-container-lg">
				<CardHeader>
					<p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
						{MODE_LABELS[preview.mode] ?? "Course"} shared with you
					</p>
					<CardTitle className="text-xl">{preview.title}</CardTitle>
					{preview.description ? <CardDescription>{preview.description}</CardDescription> : null}
				</CardHeader>
				<CardContent className="space-y-3">
					<p className="text-sm text-muted-foreground">
						{questionCountLabel(preview.questionCount)} across {conceptNames.length} concepts. Your progress starts
						fresh.
					</p>
					{shownConcepts.length > 0 ? (
						<ul className="flex flex-wrap gap-2">
							{shownConcepts.map((name) => (
								<li
									key={name}
									className="rounded-full border border-border bg-muted/40 px-3 py-1 text-xs text-foreground"
								>
									{name}
								</li>
							))}
							{hiddenConceptCount > 0 ? (
								<li className="rounded-full px-3 py-1 text-xs text-muted-foreground">+{hiddenConceptCount} more</li>
							) : null}
						</ul>
					) : null}
					{addError ? <p className="text-sm text-destructive">{addError}</p> : null}
				</CardContent>
				<CardFooter className="flex flex-wrap gap-2">
					<Button onClick={handleAdd} disabled={isAdding}>
						{isAdding ? <Loader2 className="size-4 animate-spin" /> : null}
						Add to my courses
					</Button>
					<Button variant="outline" onClick={() => navigate("/")} disabled={isAdding}>
						Not now
					</Button>
				</CardFooter>
			</Card>
		)
	}

	return <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">{body}</div>
}

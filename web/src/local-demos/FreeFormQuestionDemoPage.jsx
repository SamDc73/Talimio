import { AnimatePresence, motion } from "framer-motion"
import { ArrowRight, CheckCircle2, ChevronDown, Lightbulb, XCircle } from "lucide-react"
import { useState } from "react"
import { cn } from "@/lib/utils"

const LESSON_CONTEXT = (
	<div className="mb-8">
		<table className="w-full text-left text-sm">
			<thead className="border-b text-muted-foreground font-medium">
				<tr>
					<th className="py-3 px-2">Component</th>
					<th className="py-3 px-2">Role</th>
					<th className="py-3 px-2">Typical Mobility</th>
				</tr>
			</thead>
			<tbody className="divide-y divide-border/50">
				<tr>
					<td className="py-3 px-2 font-semibold">Phospholipids</td>
					<td className="py-3 px-2">Structural solvent</td>
					<td className="py-3 px-2">High (Lateral/Rotational)</td>
				</tr>
				<tr>
					<td className="py-3 px-2 font-semibold">Cholesterol</td>
					<td className="py-3 px-2">Fluidity buffer</td>
					<td className="py-3 px-2">Modulated (Limits extremes)</td>
				</tr>
				<tr>
					<td className="py-3 px-2 font-semibold">Integral Proteins</td>
					<td className="py-3 px-2">Transport / Signaling</td>
					<td className="py-3 px-2">Variable (Anchoring-dependent)</td>
				</tr>
				<tr>
					<td className="py-3 px-2 font-semibold">Peripheral Proteins</td>
					<td className="py-3 px-2">Signaling / Scaffold</td>
					<td className="py-3 px-2">Often tethered (Low/Regulated)</td>
				</tr>
			</tbody>
		</table>
	</div>
)

const QUESTION_TEXT =
	"Contrast the Fluid Mosaic Model with a rigid, static membrane model. Why is the concept of 'fluidity' essential for cellular function?"

const HINTS = [
	"Think about what would happen if proteins couldn't move laterally in the membrane.",
	"Consider how a cell repairs membrane damage — does a rigid shell allow that?",
	"Fluidity enables endocytosis, signal transduction, and protein diffusion. A rigid membrane would freeze all of these.",
]

const LIFTKIT_RHYTHM = {
	dense: "0.382rem",
	compact: "0.618rem",
	base: "1rem",
	section: "1.618rem",
	roomy: "2.618rem",
	label: "0.786rem",
}

function answerPlaceholder(isCompleted, hasAttempts) {
	if (isCompleted) return ""
	if (hasAttempts) return "Refine your answer..."
	return "Type your answer here..."
}

function attemptPanelClass(status) {
	if (status === "correct") return "rounded-xl border border-completed/30 bg-completed/10"
	if (status === "almost") return "rounded-xl border border-due-today/30 bg-due-today/10"
	if (!status) return ""
	return "rounded-xl border border-destructive/30 bg-destructive/10"
}

const ALMOST_FEEDBACK =
	"You're on the right track! Your answer touches on the idea but doesn't fully explain why fluidity is essential. Try being more specific about which cellular processes depend on membrane fluidity."

const CORRECT_FEEDBACK =
	"Great job! A fluid membrane allows proteins to move and interact, enabling signaling, transport, and repair. A rigid model wouldn't permit this dynamic behavior."

const INCORRECT_FEEDBACK =
	"Your answer doesn't address the difference between a static and a fluid membrane. Think about what cells need their membranes to do — transport, signaling, repair — and why rigidity would prevent that."

function evaluateAnswer(answer) {
	const lower = answer.toLowerCase().trim()
	if (lower === "yes" || lower === "true" || lower.includes("correct") || lower.includes("fluid")) {
		return { status: "correct", feedback: CORRECT_FEEDBACK }
	}
	if (lower === "yeah" || lower === "ye" || lower === "ya" || lower === "yep" || lower === "yea") {
		return { status: "almost", feedback: ALMOST_FEEDBACK }
	}
	return { status: "incorrect", feedback: INCORRECT_FEEDBACK }
}

function FeedbackIcon({ status }) {
	if (status === "correct") return <CheckCircle2 className="size-4 text-completed" />
	if (status === "almost") return <Lightbulb className="size-4 text-due-today-text" />
	return <XCircle className="size-4 text-destructive" />
}

function FeedbackLabel({ status }) {
	if (status === "correct") return <span className="text-sm font-medium text-completed">Correct</span>
	if (status === "almost") return <span className="text-sm font-medium text-due-today-text">Almost there</span>
	return <span className="text-sm font-medium text-destructive">Not quite</span>
}

// ------------------------------------------------------------------------------------------------
// Demo 1: Baseline (Current UI, confusing green for wrong)
// ------------------------------------------------------------------------------------------------
function Demo1Baseline() {
	const [answer, setAnswer] = useState("")
	const [grade, setGrade] = useState(null)

	const handleSubmit = () => {
		setGrade(evaluateAnswer(answer))
	}

	const handleReset = () => {
		setAnswer("")
		setGrade(null)
	}

	const submitted = grade !== null

	return (
		<div className="rounded-2xl border border-border/40 p-6 md:p-8 bg-card shadow-sm max-w-3xl mx-auto">
			{LESSON_CONTEXT}

			<div className="mb-6 text-lg font-medium text-foreground">
				<p>{QUESTION_TEXT}</p>
			</div>

			<div className="mb-6">
				<textarea
					value={answer}
					onChange={(e) => !submitted && setAnswer(e.target.value)}
					disabled={submitted}
					placeholder="Type 'yes' for correct, anything else for incorrect..."
					rows={4}
					className={`w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 ${
						submitted
							? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
							: "bg-background border-input focus:border-ring"
					}`}
				/>
			</div>

			{submitted ? (
				<div>
					<div className="bg-completed/10 border border-completed/30 rounded-lg mb-4 p-4">
						<div className="text-sm font-medium mb-2 text-completed">✓ Answer Submitted</div>
						<div className="text-sm/relaxed text-muted-foreground">
							<p>{grade.feedback}</p>
						</div>
					</div>

					<button
						type="button"
						onClick={handleReset}
						className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 bg-secondary text-secondary-foreground hover:bg-secondary/80 h-10 px-4 py-2"
					>
						Write Another Answer
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={!answer.trim()}
					className={`inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 ${
						!answer.trim() ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground hover:bg-primary/90"
					}`}
				>
					Submit Answer
				</button>
			)}
		</div>
	)
}

// ------------------------------------------------------------------------------------------------
// Demo 2: Semantic Colors (Clear right/wrong indicators)
// ------------------------------------------------------------------------------------------------
function Demo2Semantic() {
	const [answer, setAnswer] = useState("")
	const [grade, setGrade] = useState(null)

	const handleSubmit = () => {
		setGrade(evaluateAnswer(answer))
	}

	const handleReset = () => {
		setAnswer("")
		setGrade(null)
	}

	const submitted = grade !== null
	const isCorrect = grade?.status === "correct"

	let textareaClasses = "bg-background border-input focus:border-ring"
	if (submitted) {
		if (isCorrect) {
			textareaClasses =
				"bg-green-50/50 border-green-200 text-green-900 dark:bg-green-950/20 dark:border-green-900 dark:text-green-200"
		} else {
			textareaClasses =
				"bg-red-50/50 border-red-200 text-red-900 dark:bg-red-950/20 dark:border-red-900 dark:text-red-200"
		}
	}

	return (
		<div className="rounded-2xl border border-border/40 p-6 md:p-8 bg-card shadow-sm max-w-3xl mx-auto">
			{LESSON_CONTEXT}

			<div className="mb-6 text-lg font-medium text-foreground">
				<p>{QUESTION_TEXT}</p>
			</div>

			<div className="mb-6">
				<textarea
					value={answer}
					onChange={(e) => !submitted && setAnswer(e.target.value)}
					disabled={submitted}
					placeholder="Type 'yes' for correct, anything else for incorrect..."
					rows={4}
					className={cn(
						"w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70",
						textareaClasses
					)}
				/>
			</div>

			{submitted ? (
				<div className="animate-in fade-in slide-in-from-top-2 duration-300">
					<div
						className={cn(
							"rounded-lg mb-4 p-4 border",
							isCorrect
								? "bg-green-50 border-green-200 dark:bg-green-900/10 dark:border-green-900/50"
								: "bg-red-50 border-red-200 dark:bg-red-900/10 dark:border-red-900/50"
						)}
					>
						<div
							className={cn(
								"text-sm font-semibold mb-2 flex items-center gap-2",
								isCorrect ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"
							)}
						>
							{isCorrect ? "✓ Correct" : "✗ Needs Improvement"}
						</div>
						<div
							className={cn(
								"text-sm/relaxed",
								isCorrect ? "text-green-800 dark:text-green-300" : "text-red-800 dark:text-red-300"
							)}
						>
							<p>{grade.feedback}</p>
						</div>
					</div>

					{!isCorrect && (
						<button
							type="button"
							onClick={handleReset}
							className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring bg-secondary text-secondary-foreground hover:bg-secondary/80 h-10 px-4 py-2"
						>
							Try Again
						</button>
					)}
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={!answer.trim()}
					className={`inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 ${
						!answer.trim() ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground hover:bg-primary/90"
					}`}
				>
					Submit Answer
				</button>
			)}
		</div>
	)
}

function conversationBubbleClass(status) {
	if (status === "correct")
		return "bg-green-100/50 text-green-900 border border-green-200/50 dark:bg-green-900/20 dark:text-green-200 dark:border-green-900/50"
	if (status === "almost")
		return "bg-amber-50/50 text-amber-900 border border-amber-200/50 dark:bg-amber-900/20 dark:text-amber-200 dark:border-amber-900/50"
	return "bg-red-100/50 text-red-900 border border-red-200/50 dark:bg-red-900/20 dark:text-red-200 dark:border-red-900/50"
}

function conversationLabel(status) {
	if (status === "correct") return "✓ Correct"
	if (status === "almost") return "~ Almost"
	return "✗ Hint"
}

// ------------------------------------------------------------------------------------------------
// Demo 3: Conversational (Stacks previous attempts)
// ------------------------------------------------------------------------------------------------
function Demo3Conversational() {
	const [attempts, setAttempts] = useState([])
	const [currentAnswer, setCurrentAnswer] = useState("")

	const handleSubmit = () => {
		const result = evaluateAnswer(currentAnswer)
		setAttempts([...attempts, { id: crypto.randomUUID(), text: currentAnswer, grade: result }])
		setCurrentAnswer("")
	}

	const isCompleted = attempts.some((a) => a.grade.status === "correct")

	return (
		<div className="rounded-2xl border border-border/40 p-6 md:p-8 bg-card shadow-sm max-w-3xl mx-auto">
			{LESSON_CONTEXT}

			<div className="mb-6 text-lg font-medium text-foreground">
				<p>{QUESTION_TEXT}</p>
			</div>

			<div className="space-y-6 mb-6">
				{attempts.map((attempt) => (
					<div key={attempt.id} className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
						<div className="flex justify-end">
							<div className="bg-muted/50 border border-border/50 text-foreground px-4 py-3 rounded-2xl rounded-tr-sm text-sm max-w-[85%] whitespace-pre-wrap">
								{attempt.text}
							</div>
						</div>

						<div className="flex justify-start">
							<div
								className={cn(
									"px-4 py-3 rounded-2xl rounded-tl-sm text-sm max-w-[85%]",
									conversationBubbleClass(attempt.grade.status)
								)}
							>
								<div className="font-semibold mb-1 flex items-center gap-1.5 opacity-80 text-xs uppercase tracking-wider">
									{conversationLabel(attempt.grade.status)}
								</div>
								<div className="leading-relaxed">{attempt.grade.feedback}</div>
							</div>
						</div>
					</div>
				))}
			</div>

			{!isCompleted && (
				<div className="mt-6 border-t pt-6">
					<textarea
						value={currentAnswer}
						onChange={(e) => setCurrentAnswer(e.target.value)}
						placeholder={attempts.length > 0 ? "Try again..." : "Type your answer here..."}
						rows={3}
						className="w-full px-4 py-3 text-sm rounded-xl border bg-background border-input resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 mb-4 shadow-sm"
					/>
					<div className="flex justify-end">
						<button
							type="button"
							onClick={handleSubmit}
							disabled={!currentAnswer.trim()}
							className={`inline-flex items-center justify-center rounded-full text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-10 px-6 ${
								!currentAnswer.trim()
									? "bg-muted text-muted-foreground"
									: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm hover:shadow-sm"
							}`}
						>
							{attempts.length > 0 ? "Submit Revision" : "Submit Answer"}
						</button>
					</div>
				</div>
			)}
			{isCompleted && (
				<div className="mt-8 flex justify-center">
					<button
						type="button"
						className="inline-flex items-center justify-center rounded-full bg-primary text-primary-foreground h-10 px-6 text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm"
					>
						Continue Lesson →
					</button>
				</div>
			)}
		</div>
	)
}

function AttemptHistory({ attempts }) {
	if (attempts.length <= 1) return null

	return (
		<div className="mb-6 space-y-3">
			{attempts.slice(0, -1).map((attempt) => (
				<div key={attempt.id} className="flex items-start gap-3 text-sm">
					<div className="mt-0.5 shrink-0">
						<FeedbackIcon status={attempt.grade.status} />
					</div>
					<div className="flex-1 min-w-0">
						<div className="text-muted-foreground line-through decoration-border/60 truncate">{attempt.text}</div>
						<div className="text-muted-foreground/70 text-xs mt-0.5">
							{attempt.grade.feedback.slice(0, 100)}
							{attempt.grade.feedback.length > 100 ? "..." : ""}
						</div>
					</div>
				</div>
			))}
		</div>
	)
}

function CompactAttemptLog({ attempts }) {
	const previousAttempts = attempts.slice(0, -1)
	if (previousAttempts.length === 0) return null

	function dotClass(status) {
		if (status === "correct") return "bg-completed"
		if (status === "almost") return "bg-due-today"
		return "bg-destructive"
	}

	function statusLabel(status) {
		if (status === "correct") return "Correct"
		if (status === "almost") return "Almost"
		return "Wrong"
	}

	function statusTextClass(status) {
		if (status === "correct") return "text-completed"
		if (status === "almost") return "text-due-today-text"
		return "text-destructive"
	}

	return (
		<details className="group mb-5 [&_summary::-webkit-details-marker]:hidden">
			<summary className="inline-flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">
				<div className="flex items-center gap-1.5">
					{previousAttempts.map((attempt) => (
						<div key={attempt.id} className={cn("size-2 rounded-full", dotClass(attempt.grade.status))} />
					))}
				</div>
				<span>
					{previousAttempts.length} previous {previousAttempts.length === 1 ? "attempt" : "attempts"}
				</span>
				<ChevronDown className="size-3 transition-transform group-open:rotate-180" />
			</summary>

			<div className="mt-3 space-y-2 border-l border-border/50 pl-3">
				{previousAttempts.map((attempt) => (
					<div key={`${attempt.id}-row`} className="flex items-center gap-2 min-w-0 text-sm">
						<div className={cn("size-1.5 shrink-0 rounded-full", dotClass(attempt.grade.status))} />
						<span className="min-w-0 flex-1 truncate text-muted-foreground">{attempt.text}</span>
						<span
							className={cn(
								"shrink-0 text-[11px] font-medium uppercase tracking-wide",
								statusTextClass(attempt.grade.status)
							)}
						>
							{statusLabel(attempt.grade.status)}
						</span>
					</div>
				))}
			</div>
		</details>
	)
}

// ------------------------------------------------------------------------------------------------
// Demo 4: Progress Dots — Same inline lesson block, but with a thin
// attempt tracker. Each dot shows the state of past attempts.
// Hints auto-reveal progressively. "Almost" has its own amber dot.
// ------------------------------------------------------------------------------------------------
function Demo4ProgressDots() {
	const [answer, setAnswer] = useState("")
	const [attempts, setAttempts] = useState([])

	const handleSubmit = () => {
		const result = evaluateAnswer(answer)
		setAttempts([...attempts, { id: crypto.randomUUID(), text: answer, grade: result }])
	}

	const latestAttempt = attempts[attempts.length - 1]
	const isCompleted = latestAttempt?.grade.status === "correct"

	function hintForAttempt() {
		const wrongCount = attempts.filter((a) => a.grade.status === "incorrect").length
		if (wrongCount >= 3) return HINTS[2]
		if (wrongCount >= 2) return HINTS[1]
		if (wrongCount >= 1) return HINTS[0]
		return null
	}

	const currentHint = hintForAttempt()

	return (
		<div className="my-8 rounded-2xl border border-border/70 bg-card/80 p-6" data-askai-exclude="true">
			<p className="mb-6 text-lg font-medium text-foreground">{QUESTION_TEXT}</p>

			<CompactAttemptLog attempts={attempts} />

			<div className="mb-6">
				<textarea
					value={answer}
					onChange={(e) => setAnswer(e.target.value)}
					placeholder={answerPlaceholder(isCompleted, attempts.length > 0)}
					rows={4}
					disabled={isCompleted}
					className="w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 bg-background border-input focus:border-ring disabled:opacity-60"
				/>
			</div>

			{latestAttempt && !isCompleted && (
				<div className="mb-6 animate-in fade-in slide-in-from-top-2 duration-300">
					<div className={cn("mb-3 p-4", attemptPanelClass(latestAttempt.grade.status))}>
						<div className="flex items-center gap-2 mb-2">
							<FeedbackIcon status={latestAttempt.grade.status} />
							<FeedbackLabel status={latestAttempt.grade.status} />
						</div>
						<p className="text-sm/relaxed text-muted-foreground">{latestAttempt.grade.feedback}</p>
					</div>

					{currentHint && (
						<div className="flex items-start gap-2 text-sm text-muted-foreground py-1">
							<Lightbulb className="size-3.5 text-due-today-text mt-0.5 shrink-0" />
							<span>{currentHint}</span>
						</div>
					)}
				</div>
			)}

			{isCompleted && (
				<div className="mb-4 animate-in fade-in slide-in-from-top-2 duration-300">
					<div className="rounded-xl border border-completed/30 bg-completed/10 p-4">
						<div className="flex items-center gap-2 mb-2">
							<CheckCircle2 className="size-4 text-completed" />
							<span className="text-sm font-medium text-completed">Correct</span>
						</div>
						<p className="text-sm/relaxed text-muted-foreground">{latestAttempt.grade.feedback}</p>
					</div>
				</div>
			)}

			{!isCompleted && (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={!answer.trim()}
					className={cn(
						"rounded-lg px-4 py-2 text-sm font-medium transition-colors",
						answer.trim()
							? "bg-completed text-completed-text hover:bg-completed/90"
							: "cursor-not-allowed bg-muted text-muted-foreground"
					)}
				>
					{attempts.length > 0 ? "Submit revision" : "Submit answer"}
				</button>
			)}
		</div>
	)
}

// ------------------------------------------------------------------------------------------------
// Demo 6: Inline Refine — Compact inline block. Wrong answer shows
// feedback + "Refine" button that keeps the textarea with the previous
// answer pre-filled for editing. "Almost" gets a warm amber border
// glow on the textarea. Hints as a collapsible details element.
// ------------------------------------------------------------------------------------------------
function Demo5InlineRefine() {
	const [answer, setAnswer] = useState("")
	const [attempts, setAttempts] = useState([])

	const handleSubmit = () => {
		const result = evaluateAnswer(answer)
		setAttempts([...attempts, { id: crypto.randomUUID(), text: answer, grade: result }])
	}

	const handleRefine = (attempt) => {
		setAnswer(attempt.text)
	}

	const handleReset = () => {
		setAnswer("")
		setAttempts([])
	}

	const latestAttempt = attempts[attempts.length - 1]
	const isCompleted = latestAttempt?.grade.status === "correct"
	const status = latestAttempt?.grade.status

	function hintIndex() {
		const wrongCount = attempts.filter((a) => a.grade.status === "incorrect").length
		if (wrongCount >= 3) return 2
		if (wrongCount >= 2) return 1
		if (wrongCount >= 1) return 0
		return -1
	}

	return (
		<div className="my-8 rounded-2xl border border-border/70 bg-card/80 p-6" data-askai-exclude="true">
			<p className="mb-6 text-lg font-medium text-foreground">{QUESTION_TEXT}</p>

			<AttemptHistory attempts={attempts} />

			<div className="mb-6">
				<textarea
					value={answer}
					onChange={(e) => setAnswer(e.target.value)}
					placeholder={answerPlaceholder(isCompleted, attempts.length > 0)}
					rows={4}
					disabled={isCompleted}
					className="w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 bg-background border-input focus:border-ring disabled:opacity-60"
				/>
			</div>

			{latestAttempt && !isCompleted && (
				<div className="animate-in fade-in slide-in-from-top-2 duration-300">
					<div className={cn("mb-4 p-4", attemptPanelClass(status))}>
						<div className="flex items-center gap-2 mb-2">
							<FeedbackIcon status={status} />
							<FeedbackLabel status={status} />
						</div>
						<p className="text-sm/relaxed text-muted-foreground">{latestAttempt.grade.feedback}</p>
					</div>

					{hintIndex() >= 0 && (
						<details className="mb-4 group">
							<summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground transition-colors list-none flex items-center gap-1.5">
								<Lightbulb className="size-3.5 text-due-today-text" />
								Need a hint?
								<ChevronDown className="size-3 transition-transform group-open:rotate-180" />
							</summary>
							<div className="mt-2 flex items-start gap-2 text-sm text-muted-foreground py-2">
								<span>{HINTS[hintIndex()]}</span>
							</div>
						</details>
					)}

					<div className="flex items-center gap-3">
						<button
							type="button"
							onClick={() => handleRefine(latestAttempt)}
							className="inline-flex items-center gap-1.5 rounded-lg bg-muted px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted/80"
						>
							Refine answer
						</button>
						{attempts.length > 1 && (
							<button
								type="button"
								onClick={handleReset}
								className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
							>
								Start over
							</button>
						)}
					</div>
				</div>
			)}

			{isCompleted && (
				<div className="animate-in fade-in slide-in-from-top-2 duration-300">
					<div className={cn("mb-4 p-4", attemptPanelClass(status))}>
						<div className="flex items-center gap-2 mb-2">
							<CheckCircle2 className="size-4 text-completed" />
							<span className="text-sm font-medium text-completed">Correct</span>
						</div>
						<p className="text-sm/relaxed text-muted-foreground">{latestAttempt.grade.feedback}</p>
					</div>
				</div>
			)}

			{!isCompleted && (
				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={handleSubmit}
						disabled={!answer.trim()}
						className={cn(
							"rounded-lg px-4 py-2 text-sm font-medium transition-colors",
							answer.trim()
								? "bg-completed text-completed-text hover:bg-completed/90"
								: "cursor-not-allowed bg-muted text-muted-foreground"
						)}
					>
						{attempts.length > 0 ? "Submit revision" : "Submit answer"}
					</button>
					{attempts.length > 0 && !isCompleted && (
						<span className="text-xs text-muted-foreground font-medium">Attempt {attempts.length + 1}</span>
					)}
				</div>
			)}
		</div>
	)
}

// ------------------------------------------------------------------------------------------------
// Demo 7: Warm Coach — Same inline block but with a subtle warmth.
// "Almost there" gets a soft amber left-border accent. Feedback
// panel feels more like a tutor note than a system message.
// Wrong answers auto-reveal a hint inline. Keeps retry open.
// ------------------------------------------------------------------------------------------------
function Demo6WarmCoach() {
	const [answer, setAnswer] = useState("")
	const [attempts, setAttempts] = useState([])

	const handleSubmit = () => {
		const result = evaluateAnswer(answer)
		setAttempts([...attempts, { id: crypto.randomUUID(), text: answer, grade: result }])
	}

	const latestAttempt = attempts[attempts.length - 1]
	const isCompleted = latestAttempt?.grade.status === "correct"
	const wrongCount = attempts.filter((a) => a.grade.status === "incorrect").length
	const rhythm = LIFTKIT_RHYTHM

	function borderAccent() {
		if (!latestAttempt) return "border-l-4 border-l-transparent"
		if (latestAttempt.grade.status === "correct") return "border-l-4 border-l-completed"
		if (latestAttempt.grade.status === "almost") return "border-l-4 border-l-due-today"
		return "border-l-4 border-l-destructive"
	}

	function panelClass() {
		if (!latestAttempt) return ""
		if (latestAttempt.grade.status === "correct") return "rounded-xl border border-completed/30 bg-completed/10"
		if (latestAttempt.grade.status === "almost") return "rounded-xl border border-due-today/30 bg-due-today/10"
		return "rounded-xl border border-destructive/30 bg-destructive/10"
	}

	function hintForAttempt() {
		if (wrongCount >= 3) return HINTS[2]
		if (wrongCount >= 2) return HINTS[1]
		if (wrongCount >= 1) return HINTS[0]
		return null
	}

	const currentHint = hintForAttempt()

	return (
		<div
			className="my-8 rounded-2xl border border-border/70 bg-card/80"
			data-askai-exclude="true"
			style={{ padding: rhythm.section }}
		>
			<p className="text-lg font-medium text-foreground" style={{ marginBottom: rhythm.section }}>
				{QUESTION_TEXT}
			</p>

			<AttemptHistory attempts={attempts} />

			<div style={{ marginBottom: rhythm.section }}>
				<textarea
					value={answer}
					onChange={(e) => setAnswer(e.target.value)}
					placeholder={answerPlaceholder(isCompleted, attempts.length > 0)}
					rows={4}
					disabled={isCompleted}
					className="w-full text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 bg-background border-input focus:border-ring disabled:opacity-60"
					style={{ padding: `${rhythm.base} ${rhythm.base}` }}
				/>
			</div>

			{latestAttempt && (
				<div className="animate-in fade-in slide-in-from-top-2 duration-300" style={{ marginBottom: rhythm.section }}>
					<div className={cn(borderAccent(), panelClass())} style={{ padding: rhythm.base }}>
						<div className="flex items-center" style={{ gap: rhythm.compact, marginBottom: rhythm.compact }}>
							<FeedbackIcon status={latestAttempt.grade.status} />
							<FeedbackLabel status={latestAttempt.grade.status} />
							{latestAttempt.grade.status === "almost" && (
								<span className="text-xs text-due-today-text">just needs a bit more detail</span>
							)}
						</div>
						<p className="text-sm/relaxed text-muted-foreground">{latestAttempt.grade.feedback}</p>

						{currentHint && !isCompleted && (
							<div className="border-t border-border/50" style={{ marginTop: rhythm.base, paddingTop: rhythm.base }}>
								<p
									className="font-medium uppercase tracking-wide text-muted-foreground"
									style={{ fontSize: rhythm.label, marginBottom: rhythm.dense }}
								>
									Hint
								</p>
								<p className="text-sm/relaxed text-muted-foreground">{currentHint}</p>
							</div>
						)}
					</div>
				</div>
			)}

			{isCompleted && (
				<button
					type="button"
					className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
				>
					Continue
					<ArrowRight className="size-3.5" />
				</button>
			)}

			{!isCompleted && (
				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={handleSubmit}
						disabled={!answer.trim()}
						className={cn(
							"rounded-lg px-4 py-2 text-sm font-medium transition-colors",
							answer.trim()
								? "bg-completed text-completed-text hover:bg-completed/90"
								: "cursor-not-allowed bg-muted text-muted-foreground"
						)}
					>
						{attempts.length > 0 ? "Submit revision" : "Submit answer"}
					</button>
					{attempts.length > 0 && (
						<span className="text-xs text-muted-foreground">
							{wrongCount > 0 ? `Attempt ${attempts.length + 1}` : ""}
						</span>
					)}
				</div>
			)}
		</div>
	)
}

// ------------------------------------------------------------------------------------------------
// Demo page with tab navigation
// ------------------------------------------------------------------------------------------------
export default function FreeFormQuestionDemoPage() {
	const [activeTab, setActiveTab] = useState(0)

	const tabs = [
		{ name: "1. Baseline", component: Demo1Baseline },
		{ name: "2. Semantic", component: Demo2Semantic },
		{ name: "3. Conversational", component: Demo3Conversational },
		{ name: "4. Progress Dots", component: Demo4ProgressDots, badge: "NEW" },
		{ name: "5. Inline Refine", component: Demo5InlineRefine, badge: "NEW" },
		{ name: "6. Warm Coach", component: Demo6WarmCoach, badge: "NEW" },
	]

	const ActiveComponent = tabs[activeTab].component

	return (
		<div className="min-h-screen bg-muted/20 py-12 px-4">
			<div className="max-w-3xl mx-auto mb-10">
				<div className="mb-8">
					<h1 className="text-3xl font-bold tracking-tight mb-2">Free Form Question UI Studies</h1>
					<p className="text-muted-foreground">
						Exploring variations for the interactive question block. Type <strong>"yes"</strong> for correct,{" "}
						<strong>"yeah"</strong> or <strong>"ye"</strong> for almost there, or anything else for incorrect.
					</p>
				</div>

				<div className="flex flex-wrap gap-2 mb-8 border-b border-border pb-4">
					{tabs.map((tab, idx) => (
						<button
							key={tab.name}
							type="button"
							onClick={() => setActiveTab(idx)}
							className={cn(
								"px-4 py-2 rounded-full text-sm font-medium transition-all relative",
								activeTab === idx
									? "bg-primary text-primary-foreground shadow-sm"
									: "bg-background border hover:bg-muted text-muted-foreground"
							)}
						>
							{tab.name}
							{tab.badge && (
								<span
									className={cn(
										"ml-1.5 inline-flex items-center text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full",
										activeTab === idx
											? "bg-primary-foreground/20 text-primary-foreground"
											: "bg-primary/10 text-primary"
									)}
								>
									{tab.badge}
								</span>
							)}
						</button>
					))}
				</div>

				<AnimatePresence mode="wait">
					<motion.div
						key={activeTab}
						initial={{ opacity: 0, y: 12 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -12 }}
						transition={{ duration: 0.2 }}
					>
						<ActiveComponent />
					</motion.div>
				</AnimatePresence>
			</div>
		</div>
	)
}

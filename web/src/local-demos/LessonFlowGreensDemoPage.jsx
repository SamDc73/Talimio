import { ArrowLeft, ArrowRight, CheckCircle2, History, RotateCcw, Sparkles } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { Badge } from "@/components/Badge"
import { Button } from "@/components/Button"
import { cn } from "@/lib/utils"

const LESSON = {
	title: "Understanding Recursion in Functional Programming",
	description:
		"Explore how recursion serves as a fundamental building block in functional programming paradigms, covering tail recursion, memoization, and practical patterns.",
	windows: [
		{ id: "w1", windowIndex: 0, title: "Core Concepts" },
		{ id: "w2", windowIndex: 1, title: "Examples" },
		{ id: "w3", windowIndex: 2, title: "Exercises" },
	],
}

const RESEARCH_SIGNALS = [
	{
		title: "Green and blue-green signal positive calm",
		source: "Mohr et al., 2025 systematic review",
		detail:
			"Across 132 peer-reviewed studies, green and green-blue most consistently mapped to positive, low-arousal emotion. That supports confidence without hype.",
	},
	{
		title: "Trust rises when the surface is less saturated",
		source: "Kosova, 2024 interface-trust study",
		detail:
			"Green interfaces scored higher on initial trust, and less-saturated backgrounds tended to be trusted more than louder palettes. So the accent can pop, but the surrounding shell should stay restrained.",
	},
	{
		title: "Lightness changes the feeling fast",
		source: "Mohr et al., 2025 systematic review",
		detail:
			"Lighter colours skew more positive, while darker colours skew more negative. That pushes us away from very dark forest greens if the goal is possibility rather than seriousness.",
	},
	{
		title: "Night comfort is real, but not a free pass",
		source: "Ettling et al., 2025 and Intaruk et al., 2025",
		detail:
			"Dark themes can reduce workload or fatigue in some conditions, but overly dark or glowing accents are not universally better. Medium-lightness greens are the safer all-night zone.",
	},
]

const GREEN_PALETTES = [
	{
		id: "original",
		label: "Original green",
		spec: "oklch(0.55 0.15 142)",
		accent: "oklch(0.68 0.09 146)",
		note: "Baseline: the current primary green. High chroma, strong pull, a bit more generic app-success energy.",
		traits: ["original", "reference", "high pull"],
		suggestedBy: "Original reference",
		isOriginal: true,
	},
	{
		id: "emerald",
		label: "Balanced emerald",
		spec: "oklch(0.58 0.13 149)",
		accent: "oklch(0.7 0.08 152)",
		note: "Shifted slightly cooler and denser. Feels composed, capable, and special without losing enough contrast for the CTA.",
		traits: ["current leader", "confidence", "night-safe"],
		highlight: true,
		suggestedBy: "gpt-5.4",
	},
	{
		id: "optimistic-leaf",
		label: "Optimistic leaf",
		spec: "oklch(0.61 0.15 138)",
		accent: "oklch(0.75 0.08 142)",
		note: "Warmer than emerald and still controlled. This is the most direct translation of 'I can do it' without tipping into loud startup lime.",
		traits: ["optimistic", "confidence", "pop"],
		suggestedBy: "gpt-5.4",
	},
	{
		id: "fresh-clover",
		label: "Fresh clover",
		spec: "oklch(0.59 0.17 144)",
		accent: "oklch(0.73 0.1 147)",
		note: "Higher chroma adds immediate lift and youth. It pops harder than emerald, but it starts flirting with generic productivity-app green.",
		traits: ["pop", "youthful", "energetic"],
		suggestedBy: "gpt-5.4",
	},
	{
		id: "luminous-jade",
		label: "Luminous jade",
		spec: "oklch(0.6 0.15 153)",
		accent: "oklch(0.74 0.09 156)",
		note: "A stronger jade that still feels grown-up. This is one of the best candidates if Talimio should feel a little more ownable and alive than balanced emerald.",
		traits: ["special", "pop", "ownable"],
		suggestedBy: "gpt-5.4",
	},
	{
		id: "northstar-jade",
		label: "Northstar jade",
		spec: "oklch(0.6 0.13 157)",
		accent: "oklch(0.74 0.08 160)",
		note: "Panel-synthesis midpoint between jade and viridian. Designed to keep the special Talimio feeling while softening generic success-green and staying comfortable late at night.",
		traits: ["panel merge", "balanced", "ownable"],
		suggestedBy: "gpt-5.4",
	},
	{
		id: "guiding-jade",
		label: "Guiding jade",
		spec: "oklch(0.61 0.12 159)",
		accent: "oklch(0.75 0.07 162)",
		note: "A refined jade that lifts optimism slightly while keeping chroma restrained. It stays calm over long study sessions and keeps the blue-jade ownability of the strongest Talimio-feeling greens.",
		traits: ["new suggestion", "calm confidence", "ownable"],
		suggestedBy: "gpt-5.4",
	},
	{
		id: "nocturnal-jade",
		label: "Nocturnal Jade",
		spec: "oklch(0.58 0.14 156)",
		accent: "oklch(0.72 0.08 159)",
		note: "Gemini's tighter, slightly darker jade. It keeps the alive quality of jade but leans more nighttime and more grounded than the brighter ownable greens.",
		traits: ["panel suggestion", "night-safe", "jade edge"],
		suggestedBy: "Gemini 3.1 Pro Preview",
	},
	{
		id: "flow-mint",
		label: "Flow Mint",
		spec: "#10C99F",
		accent: "#0DA884",
		note: "A luminous mint/kinetic teal that avoids the stress of pure green. Triggers dopamine (progress) without cortisol (anxiety), creating a frictionless 'I can do this' feeling. Unique enough to own as a brand color.",
		traits: ["flow state", "frictionless", "highly ownable"],
		highlight: true,
		suggestedBy: "Gemini 3.1 Pro Preview",
	},
	{
		id: "celadon-horizon",
		label: "Celadon horizon",
		spec: "oklch(0.62 0.12 158)",
		accent: "oklch(0.76 0.07 162)",
		note: "Sonnet's lighter celadon-leaning take. More airy and positive than jade-heavy options, while still avoiding the louder optimism of lime or leaf greens.",
		traits: ["panel suggestion", "airy", "calm optimism"],
		suggestedBy: "Claude Sonnet 4.6",
	},
	{
		id: "cognitive-spring",
		label: "Cognitive Spring",
		spec: "oklch(0.64 0.11 155)",
		accent: "oklch(0.75 0.07 158)",
		note: "Gemini's gentler midpoint between celadon and jade. Slightly brighter lightness keeps it encouraging and low-pressure, with enough green-blue character to feel like Talimio instead of a generic success state.",
		traits: ["new suggestion", "gentle", "long-session safe"],
		suggestedBy: "Gemini 3.1 Pro Preview (GitHub Copilot)",
	},
	{
		id: "confidence-jade",
		label: "Confidence jade",
		spec: "oklch(0.62 0.13 155)",
		accent: "oklch(0.76 0.07 158)",
		note: "GLM's small refinement on luminous jade. It pushes the positive lightness a touch higher while holding chroma in the trust-safe zone, aiming for maximum 'I can finish this' without slipping into hype.",
		traits: ["new suggestion", "trust", "steady lift"],
		suggestedBy: "GLM-5.1 (OpenCode Go)",
	},
	{
		id: "steady-tide",
		label: "Steady tide",
		spec: "oklch(0.61 0.12 155)",
		accent: "oklch(0.75 0.07 158)",
		note: "Sonnet's split-the-difference option between Northstar jade and Celadon horizon. It keeps the optimism of lighter celadon while tightening the presence enough to work as a recognizable Talimio anchor.",
		traits: ["new suggestion", "balanced", "brand anchor"],
		suggestedBy: "Claude Sonnet 4.6",
	},
	{
		id: "viridian-signal",
		label: "Viridian signal",
		spec: "oklch(0.56 0.13 160)",
		accent: "oklch(0.7 0.07 163)",
		note: "Blue-shifted just enough to feel product-distinct and late-night friendly. Less generic than emerald, more emotionally grounded than mint.",
		traits: ["special", "night-safe", "distinct"],
		suggestedBy: "gpt-5.4",
	},
	{
		id: "mint",
		label: "Clear mint",
		spec: "oklch(0.58 0.1 160)",
		accent: "oklch(0.72 0.05 164)",
		note: "Higher lightness and a cooler hue feel fresh and optimistic, though it risks getting slightly softer than ideal.",
		traits: ["fresh", "hopeful", "airy"],
		suggestedBy: "gpt-5.4",
	},
	{
		id: "teal",
		label: "Teal-leaning green",
		spec: "oklch(0.56 0.1 168)",
		accent: "oklch(0.69 0.05 171)",
		note: "Cooler hue feels more learning-system than success-badge. This is the most distinct from generic green UI.",
		traits: ["distinct", "systemic", "cool"],
		suggestedBy: "gpt-5.4",
	},
]

const SURFACE_X = "px-6 md:px-8"
const CTA_CLASS =
	"w-full justify-center gap-[0.618rem] bg-(--color-course) text-white hover:bg-(--color-course)/90 shadow-xs sm:w-auto sm:min-w-[8.5rem]"

function stepColor(isActive, isCompleted, activeClass, completedClass, defaultClass) {
	if (isActive) return activeClass
	if (isCompleted) return completedClass
	return defaultClass
}

function MockContent() {
	return (
		<div className="space-y-4">
			<h2 className="text-xl font-semibold text-foreground">What is Recursion?</h2>
			<p className="text-sm/relaxed text-muted-foreground">
				Recursion is a technique where a function calls itself to solve smaller instances of the same problem. In
				functional programming, recursion replaces loops as the primary mechanism for iteration.
			</p>
			<h3 className="pt-2 text-lg font-medium text-foreground">Key Principles</h3>
			<ol className="list-decimal list-inside space-y-1.5 text-sm text-muted-foreground">
				<li>
					<strong className="text-foreground">Base Case</strong> - Every recursive function must have a terminating
					condition
				</li>
				<li>
					<strong className="text-foreground">Progressive Approach</strong> - Each recursive call must move closer to
					the base case
				</li>
				<li>
					<strong className="text-foreground">Composition</strong> - Recursive solutions compose naturally with other
					functions
				</li>
			</ol>
			<blockquote className="my-4 border-l-2 border-(--color-course)/30 py-1 pl-4">
				<p className="text-sm italic text-muted-foreground">
					<strong className="text-foreground not-italic">Key Insight:</strong> Memoization only helps when the same
					sub-problems repeat.
				</p>
			</blockquote>
		</div>
	)
}

function ContinueButton({ isLastSection = false, onClick, nextLabel = "Continue", className }) {
	return (
		<Button type="button" size="sm" onClick={onClick} className={cn(CTA_CLASS, className)}>
			{isLastSection ? (
				<>
					<Sparkles className="size-4" />
					Next Lesson
				</>
			) : (
				<>
					{nextLabel}
					<ArrowRight className="size-4" />
				</>
			)}
		</Button>
	)
}

function ProgressDots({ activeWindow, onWindowChange }) {
	return (
		<div className="flex flex-wrap items-center gap-[0.618rem]">
			{LESSON.windows.map((window) => {
				const isActive = window.windowIndex === activeWindow
				const isCompleted = window.windowIndex < activeWindow
				const dotSize = stepColor(isActive, isCompleted, "size-[0.5rem]", "size-[0.382rem]", "size-[0.309rem]")
				const dotColor = stepColor(
					isActive,
					isCompleted,
					"bg-(--color-course) shadow-sm",
					"bg-(--color-course)/45",
					"bg-muted-foreground/20"
				)

				return (
					<button
						key={window.id}
						type="button"
						onClick={() => onWindowChange(window.windowIndex)}
						className="flex size-[1.618rem] items-center justify-center rounded-full transition-colors hover:bg-muted/40"
						aria-label={`Go to ${window.title}`}
					>
						<span className={cn("rounded-full transition-all duration-200", dotSize, dotColor)} />
					</button>
				)
			})}
		</div>
	)
}

function FlowCardsSections() {
	const [activeWindow, setActiveWindow] = useState(0)
	const isLastActive = activeWindow === LESSON.windows.length - 1

	const getMicroSummary = (title) => {
		if (title === "Core Concepts") return "Understood principles"
		if (title === "Examples") return "Reviewed patterns"
		if (title === "Exercises") return "Completed practice"
		return "Section finished"
	}

	return (
		<div>
			<div className={cn(SURFACE_X, "space-y-[0.618rem] py-4 md:py-[1.618rem]")}>
				{LESSON.windows.map((window) => {
					const isActive = window.windowIndex === activeWindow
					const isCompleted = window.windowIndex < activeWindow
					const isLast = window.windowIndex === LESSON.windows.length - 1
					const sectionClass = isActive
						? "border-(--color-course)/20 bg-(--color-course)/3 shadow-xs"
						: "border-border/30 bg-card"
					const markerClass = stepColor(
						isActive,
						isCompleted,
						"bg-(--color-course) text-white",
						"bg-(--color-course)/12 text-(--color-course)",
						"bg-muted text-muted-foreground/60"
					)

					if (isCompleted && !isActive) {
						return (
							<button
								key={window.id}
								type="button"
								onClick={() => setActiveWindow(window.windowIndex)}
								className="flex w-full items-center justify-between gap-4 rounded-2xl border border-border/20 bg-muted/20 px-4 py-3 text-left transition-all hover:bg-muted/40"
							>
								<div className="flex items-center gap-[0.618rem]">
									<CheckCircle2 className="size-4.5 text-(--color-course)" />
									<span className="text-[0.813rem] font-medium text-muted-foreground line-through decoration-muted-foreground/30">
										{window.title}
									</span>
								</div>
								<span className="max-w-[50%] truncate text-[0.688rem] text-muted-foreground/60">
									{getMicroSummary(window.title)}
								</span>
							</button>
						)
					}

					return (
						<section
							key={window.id}
							className={cn("overflow-hidden rounded-[1.618rem] border transition-all", sectionClass)}
						>
							<button
								type="button"
								onClick={() => setActiveWindow(window.windowIndex)}
								className="flex w-full items-center justify-between gap-4 px-4 py-[0.85rem] text-left"
							>
								<div className="flex items-center gap-[0.618rem]">
									<span
										className={cn(
											"flex size-[1.618rem] items-center justify-center rounded-full text-[0.688rem] font-semibold transition-all",
											markerClass
										)}
									>
										{window.windowIndex + 1}
									</span>
									<span
										className={cn(
											"text-sm font-medium transition-colors",
											isActive ? "text-foreground" : "text-muted-foreground"
										)}
									>
										{window.title}
									</span>
								</div>
								<span className="flex size-[1.618rem] items-center justify-center">
									<span
										className={cn(
											"h-[0.382rem] w-[0.382rem] rounded-full transition-colors",
											isActive ? "bg-(--color-course)" : "bg-muted-foreground/20"
										)}
									/>
								</span>
							</button>
							{isActive && (
								<div className="border-t border-border/20 p-4 ">
									<MockContent />
									{!isLast && (
										<div className="mt-[1.618rem] border-t border-border/20 pt-[1.618rem]">
											<div className="flex justify-end">
												<ContinueButton
													nextLabel="Next"
													onClick={() => setActiveWindow(window.windowIndex + 1)}
													className="sm:min-w-[7.382rem]"
												/>
											</div>
										</div>
									)}
								</div>
							)}
						</section>
					)
				})}
			</div>

			{isLastActive && (
				<div className={cn(SURFACE_X, "pb-[1.618rem] pt-[0.618rem]")}>
					<div className="flex justify-end">
						<ContinueButton isLastSection onClick={undefined} className="sm:min-w-34" />
					</div>
				</div>
			)}

			<div className={cn(SURFACE_X, "pb-4 pt-0")}>
				<div className="flex items-center justify-center">
					<ProgressDots activeWindow={activeWindow} onWindowChange={setActiveWindow} />
				</div>
			</div>
		</div>
	)
}

function LessonFlowPreview({ palette }) {
	return (
		<section className="space-y-3">
			<div className="flex flex-wrap items-start justify-between gap-3">
				<div className="min-w-0 space-y-1">
					<div className="flex items-center gap-2">
						<h2 className="text-lg font-semibold text-foreground">{palette.label}</h2>
						<Badge variant="outline" className="text-[10px] uppercase tracking-[0.14em]">
							#45
						</Badge>
						{palette.isOriginal ? <Badge variant="secondary">Original</Badge> : null}
					</div>
					<p className="max-w-2xl text-sm text-muted-foreground">{palette.note}</p>
					<p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground/70">
						Suggested by {palette.suggestedBy}
					</p>
					<div className="flex flex-wrap gap-2 pt-1">
						{palette.traits.map((trait) => (
							<span
								key={trait}
								className="rounded-full border border-border/60 bg-muted/40 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground"
							>
								{trait}
							</span>
						))}
					</div>
					<p className="font-mono text-[11px] text-muted-foreground/70">{palette.spec}</p>
				</div>
				<div className="flex items-center gap-2">
					<span
						className="size-6 rounded-full border border-border/50 shadow-sm"
						style={{ backgroundColor: palette.spec }}
					/>
					<span
						className="size-6 rounded-full border border-border/50 shadow-sm"
						style={{ backgroundColor: palette.accent }}
					/>
				</div>
			</div>

			<div
				className="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm"
				style={{ "--color-course": palette.spec, "--color-course-accent": palette.accent }}
			>
				<div className="border-b border-border/40 bg-linear-to-br from-(--color-course)/8 via-background to-course-accent/5 px-6 pb-8 pt-6 md:px-8">
					<div className="flex flex-col gap-5">
						<div className="flex items-center justify-between gap-3">
							<div className="flex items-center gap-3">
								<Button
									variant="ghost"
									size="sm"
									className="-ml-2 gap-1.5 text-muted-foreground/60 hover:bg-transparent hover:text-foreground"
								>
									<ArrowLeft className="size-4" />
									Back
								</Button>
								<Button
									variant="ghost"
									size="sm"
									className="h-6 gap-1 px-2 text-xs text-muted-foreground/60 transition-colors hover:bg-(--color-course)/8 hover:text-(--color-course)"
								>
									<History className="size-3" />
									v2.1
								</Button>
							</div>
							<div className="flex items-center gap-2">
								<Button
									variant="ghost"
									size="sm"
									className="text-muted-foreground hover:bg-(--color-course)/8 hover:text-(--color-course)"
								>
									<RotateCcw className="size-4" />
									Regenerate
								</Button>
								<Button
									size="sm"
									className="gap-1.5 bg-(--color-course) text-white hover:bg-(--color-course)/90 shadow-xs"
								>
									Practice
								</Button>
							</div>
						</div>
						<div className="space-y-2.5">
							<h1 className="max-w-3xl text-3xl/tight font-semibold tracking-tight text-foreground md:text-4xl/tight">
								{LESSON.title}
							</h1>
							<p className="max-w-2xl text-sm/relaxed text-muted-foreground md:text-base/relaxed">
								{LESSON.description}
							</p>
						</div>
					</div>
				</div>

				<FlowCardsSections />
			</div>
		</section>
	)
}

export default function LessonFlowGreensDemoPage() {
	return (
		<div className="min-h-screen bg-background text-foreground">
			<div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 md:px-6">
				<header className="rounded-3xl border border-border bg-card p-6  shadow-sm">
					<p className="text-sm font-medium text-primary">Scratch Route</p>
					<h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">#45 Green Study</h1>
					<p className="mt-3 max-w-4xl text-base/relaxed  text-muted-foreground">
						Same interaction design as `#45 Flow cards`, repeated with different OKLCH greens so the judgment stays
						about tone and readability, not layout. Open it at <code>/#/lesson-flow-greens</code>.
					</p>
					<p className="mt-3 max-w-4xl text-sm/relaxed  text-muted-foreground">
						The palette set holds the structure constant and varies only three color-science levers: lightness for
						button contrast, chroma for calm vs. hype, and hue angle for whether the green reads like a learning system,
						a success state, or something more ownable to Talimio.
					</p>
					<div className="mt-4 flex flex-wrap gap-3 text-sm">
						<Link className="text-primary underline underline-offset-4" to="/headers">
							Back to header playground
						</Link>
						<Link className="text-primary underline underline-offset-4" to="/lesson-flow-greens">
							Reload this demo route
						</Link>
					</div>
				</header>

				<section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
					{RESEARCH_SIGNALS.map((signal) => (
						<div key={signal.title} className="rounded-2xl border border-border/60 bg-card p-4 shadow-sm">
							<p className="text-sm font-semibold text-foreground">{signal.title}</p>
							<p className="mt-1 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground/70">
								{signal.source}
							</p>
							<p className="mt-3 text-sm/relaxed  text-muted-foreground">{signal.detail}</p>
						</div>
					))}
				</section>

				<div className="grid gap-8 xl:grid-cols-2 2xl:grid-cols-3">
					{GREEN_PALETTES.map((palette) => (
						<LessonFlowPreview key={palette.id} palette={palette} />
					))}
				</div>
			</div>
		</div>
	)
}

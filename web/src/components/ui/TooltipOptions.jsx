import { Highlighter, Sparkles } from "lucide-react"
import { useRef, useState } from "react"

/**
 * OPTION 1: Minimalist Pill (Current Style)
 * Clean, simple rounded pill with icon buttons
 */
export function Option1_MinimalistPill({ handlers, selectedText, onClose, tooltipX, tooltipY }) {
	const tooltipRef = useRef(null)

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: tooltipX,
				top: tooltipY,
				zIndex: 9999,
			}}
			className="animate-in fade-in zoom-in-95 duration-200"
		>
			<div className="flex items-center gap-1 p-1 bg-background border border-border rounded-full shadow-md">
				<button
					type="button"
					onClick={() => {
						handlers?.onHighlight?.(selectedText)
						onClose()
					}}
					className="group flex items-center justify-center h-7 w-7 rounded-full transition-colors hover:bg-accent text-foreground hover:text-foreground"
					title="Highlight"
				>
					<Highlighter className="h-3.5 w-3.5 transition-transform group-hover:scale-110 group-active:scale-95" />
				</button>

				<div className="w-px h-4 bg-border/50" />

				<button
					type="button"
					onClick={() => {
						handlers?.onAskAI?.(selectedText)
						onClose()
					}}
					className="group flex items-center justify-center h-7 w-7 rounded-full transition-colors hover:bg-accent text-primary hover:text-primary"
					title="Ask AI"
				>
					<Sparkles className="h-3.5 w-3.5 transition-transform group-hover:scale-110 group-active:scale-95" />
				</button>
			</div>
		</div>
	)
}

/**
 * OPTION 2: Floating Action Buttons (FAB Style)
 * Separate circular buttons with subtle shadows
 */
export function Option2_FloatingButtons({ handlers, selectedText, onClose, tooltipX, tooltipY }) {
	const tooltipRef = useRef(null)

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: tooltipX,
				top: tooltipY,
				zIndex: 9999,
			}}
			className="animate-in fade-in slide-in-from-bottom-2 duration-300"
		>
			<div className="flex items-center gap-2">
				<button
					type="button"
					onClick={() => {
						handlers?.onHighlight?.(selectedText)
						onClose()
					}}
					className="group flex items-center justify-center h-10 w-10 bg-background border border-border rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105 active:scale-95"
					title="Highlight"
				>
					<Highlighter className="h-4 w-4 text-foreground transition-transform group-hover:rotate-12" />
				</button>

				<button
					type="button"
					onClick={() => {
						handlers?.onAskAI?.(selectedText)
						onClose()
					}}
					className="group flex items-center justify-center h-10 w-10 bg-primary text-primary-foreground rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105 active:scale-95"
					title="Ask AI"
				>
					<Sparkles className="h-4 w-4 transition-transform group-hover:rotate-12 group-hover:scale-110" />
				</button>
			</div>
		</div>
	)
}

/**
 * OPTION 3: Glass Card
 * Card-style with glassmorphism effect and labels
 */
export function Option3_GlassCard({ handlers, selectedText, onClose, tooltipX, tooltipY }) {
	const tooltipRef = useRef(null)

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: tooltipX,
				top: tooltipY,
				zIndex: 9999,
			}}
			className="animate-in fade-in zoom-in-95 duration-200"
		>
			<div className="bg-background/80 backdrop-blur-sm border border-border rounded-lg shadow-xl p-2">
				<div className="flex items-center gap-1">
					<button
						type="button"
						onClick={() => {
							handlers?.onHighlight?.(selectedText)
							onClose()
						}}
						className="group flex items-center gap-2 px-3 py-2 rounded-md hover:bg-accent transition-colors duration-200"
						title="Highlight"
					>
						<Highlighter className="h-4 w-4 text-foreground transition-transform group-hover:scale-110" />
						<span className="text-sm font-medium text-foreground">Highlight</span>
					</button>

					<div className="w-px h-6 bg-border/50" />

					<button
						type="button"
						onClick={() => {
							handlers?.onAskAI?.(selectedText)
							onClose()
						}}
						className="group flex items-center gap-2 px-3 py-2 rounded-md hover:bg-accent transition-colors duration-200"
						title="Ask AI"
					>
						<Sparkles className="h-4 w-4 text-primary transition-transform group-hover:scale-110 group-hover:rotate-12" />
						<span className="text-sm font-medium bg-gradient-to-r from-primary to-primary/80 bg-clip-text text-transparent">
							Ask AI
						</span>
					</button>
				</div>
			</div>
		</div>
	)
}

/**
 * OPTION 4: Bubble Style
 * Rounded bubble with colored backgrounds
 */
export function Option4_BubbleStyle({ handlers, selectedText, onClose, tooltipX, tooltipY }) {
	const tooltipRef = useRef(null)

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: tooltipX,
				top: tooltipY,
				zIndex: 9999,
			}}
			className="animate-in fade-in zoom-in-95 duration-200"
		>
			<div className="relative">
				{/* Bubble tail */}
				<div className="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-background border-l border-b border-border rotate-45" />

				<div className="bg-background border border-border rounded-2xl shadow-lg p-2">
					<div className="flex items-center gap-2">
						<button
							type="button"
							onClick={() => {
								handlers?.onHighlight?.(selectedText)
								onClose()
							}}
							className="group flex items-center justify-center h-8 w-8 bg-amber-50 text-amber-600 rounded-xl hover:bg-amber-100 transition-all duration-200 hover:scale-105"
							title="Highlight"
						>
							<Highlighter className="h-4 w-4 transition-transform group-hover:rotate-12" />
						</button>

						<button
							type="button"
							onClick={() => {
								handlers?.onAskAI?.(selectedText)
								onClose()
							}}
							className="group flex items-center justify-center h-8 w-8 bg-purple-50 text-purple-600 rounded-xl hover:bg-purple-100 transition-all duration-200 hover:scale-105"
							title="Ask AI"
						>
							<Sparkles className="h-4 w-4 transition-transform group-hover:rotate-12 group-hover:scale-110" />
						</button>
					</div>
				</div>
			</div>
		</div>
	)
}

/**
 * Demo component to showcase all options
 */
export function TooltipOptionsDemo() {
	const [selectedOption, setSelectedOption] = useState(1)
	const [showTooltip, setShowTooltip] = useState(false)

	const mockHandlers = {
		onHighlight: (_text) => {},
		onAskAI: (_text) => {},
	}

	const options = [
		{ id: 1, name: "Minimalist Pill", component: Option1_MinimalistPill },
		{ id: 2, name: "Floating Buttons", component: Option2_FloatingButtons },
		{ id: 3, name: "Glass Card", component: Option3_GlassCard },
		{ id: 4, name: "Bubble Style", component: Option4_BubbleStyle },
	]

	const SelectedComponent = options.find((opt) => opt.id === selectedOption)?.component

	return (
		<div className="p-8 space-y-6">
			<h2 className="text-2xl font-bold">Text Selection Tooltip Options</h2>

			{/* Option Selector */}
			<div className="flex gap-2 flex-wrap">
				{options.map((option) => (
					<button
						key={option.id}
						onClick={() => setSelectedOption(option.id)}
						className={`px-4 py-2 rounded-lg border transition-colors ${
							selectedOption === option.id
								? "bg-primary text-primary-foreground border-primary"
								: "bg-background text-foreground border-border hover:bg-accent"
						}`}
					>
						{option.name}
					</button>
				))}
			</div>

			{/* Demo Area */}
			<div className="relative border border-border rounded-lg p-8 min-h-[300px] bg-muted/30">
				<p className="text-lg leading-relaxed">
					Select some text in this paragraph to see the tooltip in action. The tooltip will appear above your selection
					with different styling based on the option you've chosen above. Try selecting different parts of this text to
					see how the tooltip behaves.
				</p>

				{/* Show selected tooltip */}
				{showTooltip && SelectedComponent && (
					<SelectedComponent
						handlers={mockHandlers}
						selectedText="selected text"
						onClose={() => setShowTooltip(false)}
						tooltipX={200}
						tooltipY={100}
					/>
				)}

				<button
					onClick={() => setShowTooltip(!showTooltip)}
					className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg"
				>
					{showTooltip ? "Hide" : "Show"} Preview
				</button>
			</div>

			{/* Description */}
			<div className="bg-background border border-border rounded-lg p-4">
				<h3 className="font-semibold mb-2">Current Option: {options.find((opt) => opt.id === selectedOption)?.name}</h3>
				<div className="text-sm text-muted-foreground space-y-1">
					{selectedOption === 1 && (
						<>
							<p>• Clean, minimal design with rounded pill container</p>
							<p>• Icon-only buttons with subtle hover effects</p>
							<p>• Uses semantic theme colors</p>
						</>
					)}
					{selectedOption === 2 && (
						<>
							<p>• Material Design inspired floating action buttons</p>
							<p>• Separate circular buttons with elevation shadows</p>
							<p>• Primary color for AI action, neutral for highlight</p>
						</>
					)}
					{selectedOption === 3 && (
						<>
							<p>• Card-style with glassmorphism backdrop blur</p>
							<p>• Includes text labels for clarity</p>
							<p>• More spacious layout with descriptive text</p>
						</>
					)}
					{selectedOption === 4 && (
						<>
							<p>• Chat bubble style with tail pointer</p>
							<p>• Colored backgrounds for each action</p>
							<p>• Playful rounded corners and hover animations</p>
						</>
					)}
				</div>
			</div>
		</div>
	)
}

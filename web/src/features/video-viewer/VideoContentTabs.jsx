import { AlignLeft, FileText } from "lucide-react"
import { useState } from "react"
import { cn } from "@/lib/utils"
import { VideoTranscriptWithErrorBoundary } from "./VideoTranscript"

export function VideoContentTabs({ video, youtubePlayerRef, onSeek, isPlaying, onTimeUpdate }) {
	const [activeTab, setActiveTab] = useState("transcript")

	const tabs = [
		{
			id: "transcript",
			label: "Transcript",
			icon: <FileText className="size-4 " />,
			badge: video.hasTranscript === false ? "Not available" : null,
		},
		{
			id: "description",
			label: "About",
			icon: <AlignLeft className="size-4 " />,
			badge: null,
		},
	]

	return (
		<div className="mt-8 rounded-xl border border-border bg-card overflow-hidden shadow-sm transition-all duration-300">
			{/* Sleek Tab Navigation */}
			<div className="relative border-b border-border bg-muted/30 p-2">
				<div className="flex gap-2 relative items-stretch">
					{tabs.map((tab) => (
						<button
							key={tab.id}
							type="button"
							onClick={() => setActiveTab(tab.id)}
							className={cn(
								"flex-1 flex items-center justify-center gap-2",
								"px-6 py-3 min-h-12",
								"bg-transparent border border-transparent rounded-lg",
								"text-muted-foreground text-sm font-medium tracking-tight",
								"cursor-pointer transition-all duration-200",
								"relative overflow-hidden whitespace-nowrap select-none",
								"hover:text-video hover:bg-video/[[]0.04[]] hover:border-video/20",
								"focus-visible:outline-2 focus-visible:outline-video focus-visible:outline-offset-2",
								"disabled:opacity-50 disabled:cursor-not-allowed",
								activeTab === tab.id && [
									"bg-video/10 text-video font-semibold",
									"border-video/30 shadow-[0_1px_3px_rgba(139,92,246,0.1)]",
								]
							)}
							disabled={tab.badge === "Coming soon"}
						>
							{tab.icon}
							<span className="font-medium tracking-tight">{tab.label}</span>
							{tab.badge && (
								<span className="text-[10px] px-1.5 py-0.5 ml-1 rounded-sm bg-muted text-muted-foreground font-medium uppercase">
									{tab.badge}
								</span>
							)}
						</button>
					))}
				</div>

				{/* Tab indicator line */}
				<div
					className="absolute bottom-0 left-2 w-[calc(50%-0.75rem)] h-0.5 bg-video rounded-t transition-transform duration-300"
					style={{
						transform: `translateX(${activeTab === "transcript" ? "0%" : "calc(100% + 0.5rem)"})`,
					}}
				/>
			</div>

			{/* Tab Content */}
			<div className="relative min-h-100 rounded-b-xl bg-card overflow-hidden">
				{/* Transcript Tab */}
				<div
					className={cn(
						"absolute top-0 left-0 right-0",
						"opacity-0 invisible translate-y-2",
						"transition-all duration-300 pointer-events-none",
						activeTab === "transcript" && ["relative opacity-100 visible translate-y-0 pointer-events-auto"]
					)}
				>
					<VideoTranscriptWithErrorBoundary
						key={video.id}
						videoId={video.id}
						youtubePlayerRef={youtubePlayerRef}
						onSeek={onSeek}
						isPlaying={isPlaying}
						onTimeUpdate={onTimeUpdate}
					/>
				</div>

				{/* Description Tab */}
				<div
					className={cn(
						"absolute top-0 left-0 right-0",
						"opacity-0 invisible translate-y-2",
						"transition-all duration-300 pointer-events-none",
						activeTab === "description" && ["relative opacity-100 visible translate-y-0 pointer-events-auto p-6"]
					)}
				>
					{video.description ? (
						<div className="max-w-none">
							<p className="whitespace-pre-wrap text-sm/relaxed text-foreground/90  max-h-[400px] overflow-y-auto pr-2">
								{video.description}
							</p>
						</div>
					) : (
						<div className="flex flex-col items-center justify-center py-[60px] text-center gap-4">
							<AlignLeft className="size-12  text-muted-foreground opacity-20" />
							<p className="text-[15px] opacity-70 font-medium text-muted-foreground">No description available</p>
						</div>
					)}
				</div>
			</div>
		</div>
	)
}

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
			icon: <FileText className="w-4 h-4" />,
			badge: video.hasTranscript !== false ? null : "Not available",
		},
		{
			id: "description",
			label: "About",
			icon: <AlignLeft className="w-4 h-4" />,
			badge: null,
		},
	]

	return (
		<div className="mt-8 bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm transition-all duration-300">
			{/* Sleek Tab Navigation */}
			<div className="relative bg-gray-100/30 border-b border-gray-200 p-2">
				<div className="flex gap-2 relative items-stretch">
					{tabs.map((tab) => (
						<button
							key={tab.id}
							type="button"
							onClick={() => setActiveTab(tab.id)}
							className={cn(
								"flex-1 flex items-center justify-center gap-2",
								"px-6 py-3 min-h-[3rem]",
								"bg-transparent border border-transparent rounded-lg",
								"text-gray-100-foreground text-sm font-medium tracking-tight",
								"cursor-pointer transition-all duration-200",
								"relative overflow-hidden whitespace-nowrap select-none",
								"hover:text-violet-600 hover:bg-violet-600/[0.04] hover:border-violet-600/20",
								"focus-visible:outline-2 focus-visible:outline-violet-600 focus-visible:outline-offset-2",
								"disabled:opacity-50 disabled:cursor-not-allowed",
								activeTab === tab.id && [
									"bg-violet-600/10 text-violet-600 font-semibold",
									"border-violet-600/30 shadow-[0_1px_3px_rgba(139,92,246,0.1)]",
								]
							)}
							disabled={tab.badge === "Coming soon"}
						>
							{tab.icon}
							<span className="font-medium tracking-tight">{tab.label}</span>
							{tab.badge && (
								<span className="text-[10px] px-1.5 py-0.5 ml-1 rounded bg-gray-100 text-gray-100-foreground font-medium uppercase">
									{tab.badge}
								</span>
							)}
						</button>
					))}
				</div>

				{/* Tab indicator line */}
				<div
					className="absolute bottom-0 left-2 w-[calc(50%-0.75rem)] h-0.5 bg-violet-600 rounded-t transition-transform duration-300"
					style={{
						transform: `translateX(${activeTab === "transcript" ? "0%" : "calc(100% + 0.5rem)"})`,
					}}
				/>
			</div>

			{/* Tab Content */}
			<div className="relative min-h-[25rem] bg-white rounded-b-xl overflow-hidden">
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
							<p className="whitespace-pre-wrap leading-relaxed text-gray-900/90 text-sm max-h-[400px] overflow-y-auto pr-2">
								{video.description}
							</p>
						</div>
					) : (
						<div className="flex flex-col items-center justify-center py-[60px] text-center gap-4">
							<AlignLeft className="w-12 h-12 text-gray-100-foreground opacity-20" />
							<p className="text-[15px] opacity-70 font-medium text-gray-100-foreground">No description available</p>
						</div>
					)}
				</div>
			</div>
		</div>
	)
}

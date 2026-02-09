import { MessageSquare, PanelRight } from "lucide-react"
import { Link } from "react-router-dom"
import { UserAvatarMenu } from "@/components/header/MainHeader"
import { TooltipButton } from "@/components/TooltipButton"
import { useChatSidebar } from "@/contexts/ChatSidebarContext"
import { useVideoProgress } from "@/features/video-viewer/hooks/use-video-progress"
import { formatProgressText } from "@/utils/progressUtils"

export function VideoHeader({ video, onToggleSidebar, isSidebarOpen }) {
	const { toggleChat } = useChatSidebar()

	const { progress } = useVideoProgress(video?.id)

	return (
		<header className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-md border-b border-border shadow-sm">
			<div className="container mx-auto px-4">
				<div className="flex h-16 items-center">
					<div className="shrink-0 mr-4">
						<Link to="/" className="block">
							<img src="/logo.png" alt="Talimio Logo" width={32} height={32} className="object-contain" />
						</Link>
					</div>

					<div className="h-8 w-px bg-border mx-3" />

					<div className="flex-1 min-w-0">
						<h1 className="text-base font-semibold text-foreground truncate">{video?.title || "Loading..."}</h1>
						{video && (
							<div className="flex items-center mt-1">
								<div className="w-32 md:w-48 bg-muted rounded-full h-1.5 overflow-hidden">
									<div
										className="h-full bg-linear-to-r from-violet-500 to-violet-600 rounded-full transition-all duration-300"
										style={{ width: `${progress.percentage}%` }}
									/>
								</div>
								<span className="ml-2 text-xs font-medium text-muted-foreground">
									{formatProgressText(progress.percentage)}
								</span>
								<span className="ml-3 text-xs text-muted-foreground">{video.channelName || video.channel}</span>
							</div>
						)}
					</div>

					<div className="flex items-center gap-2">
						{onToggleSidebar && (
							<div className="hidden md:block">
								<TooltipButton
									variant="outline"
									size="icon"
									className="size-8  rounded-full"
									onClick={onToggleSidebar}
									tooltipContent={`${isSidebarOpen ? "Hide" : "Show"} chapters`}
								>
									<PanelRight
										className={`size-4  transition-transform duration-300 ${isSidebarOpen ? "" : "rotate-180"}`}
									/>
								</TooltipButton>
							</div>
						)}

						<TooltipButton
							onClick={toggleChat}
							variant="outline"
							size="icon"
							className="size-8  rounded-full"
							tooltipContent="Chat with AI assistant"
						>
							<MessageSquare className="size-4 " />
						</TooltipButton>

						<div className="ml-1">
							<UserAvatarMenu />
						</div>
					</div>
				</div>
			</div>
		</header>
	)
}

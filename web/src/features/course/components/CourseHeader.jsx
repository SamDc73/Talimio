import { Files, FileText, GitBranch, MessageSquare, PanelLeft } from "lucide-react"
import { Link } from "react-router-dom"
import { UserAvatarMenu } from "@/components/header/MainHeader"
import { TooltipButton } from "@/components/TooltipButton"
import { useChatSidebar } from "@/contexts/ChatSidebarContext"
import { useCourseProgress } from "@/features/course/hooks/use-course-progress"
import { cn } from "@/lib/utils"

export function CourseHeader({
	courseName,
	mode,
	onModeChange,
	progress = 0,
	isOpen = true,
	toggleSidebar = () => {},
	courseId,
	adaptiveEnabled = false,
}) {
	const { toggleChat } = useChatSidebar()

	const { progress: courseProgress } = useCourseProgress(courseId)
	let computedProgressRaw = progress
	if (!adaptiveEnabled && typeof courseProgress?.percentage === "number") {
		computedProgressRaw = courseProgress.percentage
	}
	const computedProgress = Math.max(
		0,
		Math.min(100, Math.round(Number.isFinite(computedProgressRaw) ? computedProgressRaw : 0))
	)
	let nextModeLabel = "Outline"
	let currentModeIcon = <Files className="size-4 " />
	if (mode === "outline") {
		nextModeLabel = "Track"
		currentModeIcon = <FileText className="size-4 " />
	} else if (mode === "track") {
		nextModeLabel = "Documents"
		currentModeIcon = <GitBranch className="size-4 " />
	}

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
						<h1 className="text-base font-semibold text-foreground truncate">{courseName}</h1>
						<div className="flex items-center mt-1">
							<div className="w-32 md:w-48 bg-muted rounded-full h-1.5 overflow-hidden">
								<div
									className="h-full bg-linear-to-r from-course to-course-accent rounded-full"
									style={{ width: `${computedProgress}%` }}
								/>
							</div>
							<span className="ml-2 text-xs font-medium text-muted-foreground">{computedProgress}%</span>
						</div>
					</div>

					<div className="hidden md:flex items-center border border-border rounded-full h-8 px-1 mx-4 bg-muted/50">
						<button
							className={cn(
								"px-3 py-1 text-xs font-medium rounded-full transition-colors",
								mode === "outline" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
							)}
							type="button"
							onClick={() => mode !== "outline" && onModeChange("outline")}
							aria-pressed={mode === "outline"}
						>
							<FileText className="size-3.5  inline-block mr-1" />
							<span>Outline</span>
						</button>
						<button
							className={cn(
								"px-3 py-1 text-xs font-medium rounded-full transition-colors",
								mode === "track" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
							)}
							type="button"
							onClick={() => mode !== "track" && onModeChange("track")}
							aria-pressed={mode === "track"}
						>
							<GitBranch className="size-3.5  inline-block mr-1" />
							<span>Track</span>
						</button>
						<button
							className={cn(
								"px-3 py-1 text-xs font-medium rounded-full transition-colors",
								mode === "documents"
									? "bg-card text-foreground shadow-sm"
									: "text-muted-foreground hover:text-foreground"
							)}
							type="button"
							onClick={() => mode !== "documents" && onModeChange("documents")}
							aria-pressed={mode === "documents"}
						>
							<Files className="size-3.5  inline-block mr-1" />
							<span>Documents</span>
						</button>
					</div>

					<div className="flex items-center gap-2">
						<div className="md:hidden">
							<TooltipButton
								variant="outline"
								size="icon"
								className="size-8  rounded-full"
								onClick={() => {
									const modes = ["outline", "track", "documents"]
									const currentIndex = modes.indexOf(mode)
									const nextIndex = (currentIndex + 1) % modes.length
									onModeChange(modes[nextIndex])
								}}
								tooltipContent={`Switch View (${nextModeLabel} next)`}
							>
								{currentModeIcon}
							</TooltipButton>
						</div>

						<TooltipButton
							variant="outline"
							size="icon"
							className="size-8  rounded-full"
							onClick={toggleSidebar}
							tooltipContent={`${isOpen ? "Hide" : "Show"} sidebar`}
						>
							<PanelLeft className={`size-4  transition-transform duration-300 ${isOpen ? "" : "rotate-180"}`} />
						</TooltipButton>

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

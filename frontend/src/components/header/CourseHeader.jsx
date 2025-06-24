import { FileText, GitBranch, MessageSquare, PanelLeft, Files } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { cn } from "../../lib/utils";
import { Button } from "../button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "../tooltip";
import { useChatSidebar } from "./MainHeader";
import { UserAvatarMenu } from "./MainHeader";

export function CourseHeader({
	courseName,
	mode,
	onModeChange,
	courseId,
	progress = 0,
	isOpen = true,
	toggleSidebar = () => {},
}) {
	const { toggleChat } = useChatSidebar();
	const [_showFullTitle, _setShowFullTitle] = useState(false);

	return (
		<header className="fixed top-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-md border-b border-border shadow-sm">
			<div className="container mx-auto px-4">
				<div className="flex h-16 items-center">
					{/* Logo Section */}
					<div className="flex-shrink-0 mr-4">
						<Link to="/" className="block">
							<img
								src="/logo.png"
								alt="Talimio Logo"
								width={32}
								height={32}
								className="object-contain"
							/>
						</Link>
					</div>

					{/* Divider */}
					<div className="h-8 w-px bg-slate-200 mx-3" />

					{/* Course Info Section */}
					<div className="flex-1 min-w-0">
						<h1 className="text-base font-semibold text-foreground truncate">
							{courseName}
						</h1>
						<div className="flex items-center mt-1">
							<div className="w-32 md:w-48 bg-muted rounded-full h-1.5 overflow-hidden">
								<div
									className="h-full bg-gradient-to-r from-course to-course-accent rounded-full"
									style={{ width: `${progress}%` }}
								/>
							</div>
							<span className="ml-2 text-xs font-medium text-muted-foreground">
								{progress}%
							</span>
						</div>
					</div>

					{/* View Toggle Section */}
					<div className="hidden md:flex items-center border border-border rounded-full h-8 px-1 mx-4 bg-slate-50/50">
						<button
							className={cn(
								"px-3 py-1 text-xs font-medium rounded-full transition-colors",
								mode === "outline"
									? "bg-white text-foreground shadow-sm"
									: "text-slate-500 hover:text-slate-700",
							)}
							type="button"
							onClick={() => mode !== "outline" && onModeChange("outline")}
							aria-pressed={mode === "outline"}
						>
							<FileText className="w-3.5 h-3.5 inline-block mr-1" />
							<span>Outline</span>
						</button>
						<button
							className={cn(
								"px-3 py-1 text-xs font-medium rounded-full transition-colors",
								mode === "track"
									? "bg-white text-foreground shadow-sm"
									: "text-slate-500 hover:text-slate-700",
							)}
							type="button"
							onClick={() => mode !== "track" && onModeChange("track")}
							aria-pressed={mode === "track"}
						>
							<GitBranch className="w-3.5 h-3.5 inline-block mr-1" />
							<span>Track</span>
						</button>
						<button
							className={cn(
								"px-3 py-1 text-xs font-medium rounded-full transition-colors",
								mode === "documents"
									? "bg-white text-foreground shadow-sm"
									: "text-slate-500 hover:text-slate-700",
							)}
							type="button"
							onClick={() => mode !== "documents" && onModeChange("documents")}
							aria-pressed={mode === "documents"}
						>
							<Files className="w-3.5 h-3.5 inline-block mr-1" />
							<span>Documents</span>
						</button>
					</div>

					{/* Actions Section */}
					<div className="flex items-center gap-2">
						{/* Mobile View Toggle */}
						<div className="md:hidden">
							<TooltipProvider>
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											variant="outline"
											size="icon"
											className="h-8 w-8 rounded-full"
											onClick={() => {
												const modes = ["outline", "track", "documents"];
												const currentIndex = modes.indexOf(mode);
												const nextIndex = (currentIndex + 1) % modes.length;
												onModeChange(modes[nextIndex]);
											}}
										>
											{mode === "outline" ? (
												<FileText className="h-4 w-4" />
											) : mode === "track" ? (
												<GitBranch className="h-4 w-4" />
											) : (
												<Files className="h-4 w-4" />
											)}
										</Button>
									</TooltipTrigger>
									<TooltipContent>
										<p>
											Switch View ({mode === "outline" ? "Track" : mode === "track" ? "Documents" : "Outline"} next)
										</p>
									</TooltipContent>
								</Tooltip>
							</TooltipProvider>
						</div>

						{/* Sidebar Toggle */}
						<TooltipProvider>
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="outline"
										size="icon"
										className="h-8 w-8 rounded-full"
										onClick={toggleSidebar}
									>
										<PanelLeft
											className={`h-4 w-4 transition-transform duration-300 ${isOpen ? "" : "rotate-180"}`}
										/>
									</Button>
								</TooltipTrigger>
								<TooltipContent>
									<p>{isOpen ? "Hide" : "Show"} sidebar</p>
								</TooltipContent>
							</Tooltip>
						</TooltipProvider>

						{/* Chat Button */}
						<TooltipProvider>
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										onClick={toggleChat}
										variant="outline"
										size="icon"
										className="h-8 w-8 rounded-full"
									>
										<MessageSquare className="h-4 w-4" />
									</Button>
								</TooltipTrigger>
								<TooltipContent>
									<p>Chat with AI assistant</p>
								</TooltipContent>
							</Tooltip>
						</TooltipProvider>

						{/* User Avatar */}
						<div className="ml-1">
							<UserAvatarMenu />
						</div>
					</div>
				</div>
			</div>
		</header>
	);
}

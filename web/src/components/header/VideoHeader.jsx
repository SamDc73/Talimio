import { MessageSquare, PanelRight } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/tooltip";
import { formatProgressText, getVideoProgress } from "@/utils/progressUtils";
import { UserAvatarMenu, useChatSidebar } from "./MainHeader";

export function VideoHeader({ video, onToggleSidebar, isSidebarOpen }) {
	const _navigate = useNavigate();
	const { toggleChat } = useChatSidebar();

	// Calculate progress percentage for display
	const progress = getVideoProgress(video);

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

					{/* Video Info Section */}
					<div className="flex-1 min-w-0">
						<h1 className="text-base font-semibold text-slate-800 truncate">
							{video?.title || "Loading..."}
						</h1>
						{video && (
							<div className="flex items-center mt-1">
								<div className="w-32 md:w-48 bg-slate-200 rounded-full h-1.5 overflow-hidden">
									<div
										className="h-full bg-gradient-to-r from-red-500 to-pink-500 rounded-full transition-all duration-300"
										style={{ width: `${progress}%` }}
									/>
								</div>
								<span className="ml-2 text-xs font-medium text-slate-600">
									{formatProgressText(progress)}
								</span>
								<span className="ml-3 text-xs text-slate-500">
									{video.channelName || video.channel}
								</span>
							</div>
						)}
					</div>

					{/* Actions Section */}
					<div className="flex items-center gap-2">
						{/* Sidebar Toggle (Desktop only) */}
						{onToggleSidebar && (
							<div className="hidden md:block">
								<TooltipProvider>
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="outline"
												size="icon"
												className="h-8 w-8 rounded-full"
												onClick={onToggleSidebar}
											>
												<PanelRight
													className={`h-4 w-4 transition-transform duration-300 ${!isSidebarOpen ? "rotate-180" : ""}`}
												/>
											</Button>
										</TooltipTrigger>
										<TooltipContent>
											<p>{isSidebarOpen ? "Hide" : "Show"} chapters</p>
										</TooltipContent>
									</Tooltip>
								</TooltipProvider>
							</div>
						)}

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

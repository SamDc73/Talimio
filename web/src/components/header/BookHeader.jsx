import { BookOpen, Maximize, MessageSquare, PanelLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "../button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "../tooltip";
import { UserAvatarMenu, useChatSidebar } from "./MainHeader";

export function BookHeader({
	bookTitle,
	bookAuthor,
	currentPage = 1,
	totalPages = 0,
	progressPercentage = 0, // Use the reliable progress percentage
	isOpen = true,
	toggleSidebar = () => {},
	onZoomIn = () => {},
	onZoomOut = () => {},
	onFitToScreen = () => {},
	zoomLevel = 100,
	showZoomControls = false,
}) {
	const { toggleChat } = useChatSidebar();

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

					{/* Book Info Section */}
					<div className="flex-1 min-w-0">
						<h1 className="text-base font-semibold text-slate-800 truncate">
							{bookTitle}
						</h1>
						<div className="flex items-center mt-1">
							{bookAuthor && (
								<span className="text-xs text-slate-600 mr-3">
									by {bookAuthor}
								</span>
							)}
							<div className="flex items-center">
								<BookOpen className="w-3 h-3 text-slate-500 mr-1" />
								<span className="text-xs text-slate-600">
									{totalPages > 0 && currentPage > 0
										? `Page ${currentPage} of ${totalPages}`
										: "Loading..."}
								</span>
								{progressPercentage > 0 && (
									<span className="ml-2 text-xs font-medium text-slate-600">
										({progressPercentage}%)
									</span>
								)}
							</div>
						</div>
					</div>

					{/* Actions Section */}
					<div className="flex items-center gap-2">
						{/* Zoom Controls for PDF */}
						{showZoomControls && (
							<div className="flex items-center border border-border rounded-full h-8 px-1 bg-muted/50">
								<TooltipProvider>
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-6 w-6 rounded-full"
												onClick={onZoomOut}
											>
												<span className="text-sm font-medium">-</span>
											</Button>
										</TooltipTrigger>
										<TooltipContent>
											<p>Zoom out</p>
										</TooltipContent>
									</Tooltip>
								</TooltipProvider>
								<span className="px-2 text-xs font-medium text-slate-600 min-w-[3rem] text-center">
									{zoomLevel}%
								</span>
								<TooltipProvider>
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-6 w-6 rounded-full"
												onClick={onZoomIn}
											>
												<span className="text-sm font-medium">+</span>
											</Button>
										</TooltipTrigger>
										<TooltipContent>
											<p>Zoom in</p>
										</TooltipContent>
									</Tooltip>
								</TooltipProvider>
								<TooltipProvider>
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-6 w-6 rounded-full ml-1"
												onClick={onFitToScreen}
											>
												<Maximize className="h-3 w-3" />
											</Button>
										</TooltipTrigger>
										<TooltipContent>
											<p>Fit to screen</p>
										</TooltipContent>
									</Tooltip>
								</TooltipProvider>
							</div>
						)}

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

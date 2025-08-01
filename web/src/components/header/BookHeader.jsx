import { Maximize, MessageSquare, PanelLeft } from "lucide-react";
import { memo } from "react";
import { Link } from "react-router-dom";
import { TooltipButton } from "@/components/TooltipButton";
import { useChatSidebar } from "@/hooks/useChatSidebar";
import { formatProgressText } from "@/utils/progressUtils";
import { UserAvatarMenu } from "./MainHeader";

export const BookHeader = memo(function BookHeader({
	book,
	onToggleSidebar,
	isSidebarOpen,
	onZoomIn = () => {},
	onZoomOut = () => {},
	onFitToScreen = () => {},
	zoomLevel = 100,
	showZoomControls = false,
}) {
	const { toggleChat } = useChatSidebar();

	// TEMPORARY: Disable useBookProgress to debug infinite loop
	// const bookId = book?.id;
	// const { progress, metadata } = useBookProgress(bookId);
	// const currentPage = metadata?.currentPage || 1;
	// const totalPages = metadata?.totalPages || book?.totalPages || 0;

	// Use fallback values for now
	const progress = { percentage: 0 };
	const currentPage = 1;
	const totalPages = book?.totalPages || 0;

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
							{book?.title || "Loading..."}
						</h1>
						{book && (
							<div className="flex items-center mt-1">
								<div className="w-32 md:w-48 bg-slate-200 rounded-full h-1.5 overflow-hidden">
									<div
										className="h-full bg-gradient-to-r from-blue-400 to-blue-500 rounded-full transition-all duration-300"
										style={{ width: `${progress.percentage}%` }}
									/>
								</div>
								<span className="ml-2 text-xs font-medium text-slate-600">
									{formatProgressText(progress.percentage)}
								</span>
								<span className="ml-3 text-xs text-slate-500">
									{totalPages > 0 && currentPage > 0
										? `Page ${currentPage} of ${totalPages}`
										: book.author || ""}
								</span>
							</div>
						)}
					</div>

					{/* Actions Section */}
					<div className="flex items-center gap-2">
						{/* Zoom Controls for PDF */}
						{showZoomControls && (
							<div className="flex items-center border border-border rounded-full h-8 px-1 bg-muted/50">
								<TooltipButton
									variant="ghost"
									size="icon"
									className="h-6 w-6 rounded-full"
									onClick={onZoomOut}
									tooltipContent="Zoom out"
								>
									<span className="text-sm font-medium">-</span>
								</TooltipButton>
								<span className="px-2 text-xs font-medium text-slate-600 min-w-[3rem] text-center">
									{zoomLevel}%
								</span>
								<TooltipButton
									variant="ghost"
									size="icon"
									className="h-6 w-6 rounded-full"
									onClick={onZoomIn}
									tooltipContent="Zoom in"
								>
									<span className="text-sm font-medium">+</span>
								</TooltipButton>
								<TooltipButton
									variant="ghost"
									size="icon"
									className="h-6 w-6 rounded-full ml-1"
									onClick={onFitToScreen}
									tooltipContent="Fit to screen"
								>
									<Maximize className="h-3 w-3" />
								</TooltipButton>
							</div>
						)}

						{/* Sidebar Toggle */}
						{onToggleSidebar && (
							<TooltipButton
								variant="outline"
								size="icon"
								className="h-8 w-8 rounded-full"
								onClick={onToggleSidebar}
								tooltipContent={`${isSidebarOpen ? "Hide" : "Show"} chapters`}
							>
								<PanelLeft
									className={`h-4 w-4 transition-transform duration-300 ${isSidebarOpen ? "" : "rotate-180"}`}
								/>
							</TooltipButton>
						)}

						{/* Chat Button */}
						<TooltipButton
							onClick={toggleChat}
							variant="outline"
							size="icon"
							className="h-8 w-8 rounded-full"
							tooltipContent="Chat with AI assistant"
						>
							<MessageSquare className="h-4 w-4" />
						</TooltipButton>

						{/* User Avatar */}
						<div className="ml-1">
							<UserAvatarMenu />
						</div>
					</div>
				</div>
			</div>
		</header>
	);
});

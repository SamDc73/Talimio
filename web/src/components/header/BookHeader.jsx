import { Maximize, MessageSquare, PanelLeft, Type } from "lucide-react"
// No useEffect needed
import { Link } from "react-router-dom"
import { TooltipButton } from "@/components/TooltipButton"
import { useChatSidebar } from "@/features/assistant/contexts/chatSidebarContext"
import useAppStore from "@/stores/useAppStore"
import { formatProgressText } from "@/utils/progressUtils"
import { UserAvatarMenu } from "./MainHeader"

export function BookHeader({
  book,
  bookId, // Always use explicit bookId from parent
  onToggleSidebar,
  isSidebarOpen,
  onZoomIn = () => {},
  onZoomOut = () => {},
  onFitToScreen = () => {},
  zoomLevel = 100,
  showZoomControls = false,
  showFontControls = false,
  onFontIncrease = () => {},
  onFontDecrease = () => {},
  fontSize = 100,
}) {
  const { toggleChat } = useChatSidebar()

  // Use the bookId passed from parent component (BookViewer) which knows the URL param
  // This ensures consistency across all components
  const isEpub = (book?.fileType?.toLowerCase?.() || "") === "epub"
  const currentPage = useAppStore((state) => state.books?.readingState?.[bookId]?.currentPage || 1)
  const storedTotalPages = useAppStore((state) => state.books?.readingState?.[bookId]?.totalPages)
  const totalPages = storedTotalPages || book?.totalPages || 0
  // For EPUB, progress is tracked via epubState.progress (0-100). Fallback to books.progress slice.
  const epubProgressFromReading = useAppStore(
    (state) => state.books?.readingState?.[bookId]?.epubState?.progress
  )
  const epubProgressFromSlice = useAppStore((state) => state.books?.progress?.[bookId]?.percentage)
  const epubProgressPct =
    (typeof epubProgressFromReading === "number" ? epubProgressFromReading : undefined) ??
    (typeof epubProgressFromSlice === "number" ? epubProgressFromSlice : undefined) ??
    0
  const progressPercentage = isEpub
    ? epubProgressPct
    : totalPages
    ? Math.round((currentPage / totalPages) * 100)
    : 0
  // Derive a display page for EPUB from percentage and known totalPages
  const displayCurrentPage = isEpub && totalPages
    ? Math.max(1, Math.min(totalPages, Math.round((progressPercentage / 100) * totalPages)))
    : currentPage
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-md border-b border-gray-200 shadow-sm">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center">
          {/* Logo Section */}
          <div className="flex-shrink-0 mr-4">
            <Link to="/" className="block">
              <img src="/logo.png" alt="Talimio Logo" width={32} height={32} className="object-contain" />
            </Link>
          </div>

          {/* Divider */}
          <div className="h-8 w-px bg-slate-200 mx-3" />

          {/* Book Info Section */}
          <div className="flex-1 min-w-0">
            <h1 className="text-base font-semibold text-slate-800 truncate">{book?.title || "Loading..."}</h1>
            {book && (
              <div className="flex items-center mt-1">
                <div className="w-32 md:w-48 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-400 to-blue-500 rounded-full transition-all duration-300"
                    style={{ width: `${progressPercentage}%` }}
                  />
                </div>
                <span className="ml-2 text-xs font-medium text-slate-600">
                  {formatProgressText(progressPercentage)}
                </span>
                <span className="ml-3 text-xs text-slate-500">
                  {totalPages > 0 && displayCurrentPage > 0 ? `Page ${displayCurrentPage} of ${totalPages}` : book.author || ""}
                </span>
              </div>
            )}
          </div>

          {/* Actions Section */}
          <div className="flex items-center gap-2">
            {/* Zoom Controls for PDF */}
						{showZoomControls && (
							<div className="flex items-center border border-gray-200 rounded-full h-8 px-1 bg-gray-100/50">
								<TooltipButton
									variant="ghost"
									size="icon"
									className="h-6 w-6 rounded-full"
									onClick={onZoomOut}
									tooltipContent="Zoom out"
								>
									<span className="text-sm font-medium">-</span>
								</TooltipButton>
								<span className="px-2 text-xs font-medium text-slate-600 min-w-[3rem] text-center">{zoomLevel}%</span>
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

						{/* Font Size Controls for EPUB */}
						{showFontControls && (
							<div className="flex items-center border border-gray-200 rounded-full h-8 px-1 bg-gray-100/50">
								<TooltipButton
									variant="ghost"
									size="icon"
									className="h-6 w-6 rounded-full"
									onClick={onFontDecrease}
									tooltipContent="Decrease font size"
								>
									<span className="text-sm font-medium">A-</span>
								</TooltipButton>
								<div className="px-2 flex items-center gap-1">
									<Type className="h-3 w-3 text-slate-600" />
									<span className="text-xs font-medium text-slate-600 min-w-[2.5rem] text-center">{fontSize}%</span>
								</div>
								<TooltipButton
									variant="ghost"
									size="icon"
									className="h-6 w-6 rounded-full"
									onClick={onFontIncrease}
									tooltipContent="Increase font size"
								>
									<span className="text-sm font-medium">A+</span>
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
	)
}

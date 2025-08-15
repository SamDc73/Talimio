import { AnimatePresence, motion } from "framer-motion"
import {
	BookOpen,
	Bot,
	Brain,
	FileText,
	GripVertical,
	Layers,
	LogOut,
	Menu,
	MessageSquare,
	Mic,
	Paperclip,
	Pin,
	PinOff,
	Search,
	Send,
	Settings,
	Sparkles,
	User,
	X,
	Youtube,
} from "lucide-react"
import { createContext, useEffect, useRef, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "@/hooks/useAuth"
import { useChatSidebar } from "@/hooks/useChatSidebar"
import { useTheme } from "../../contexts/ThemeContext"
import { useCurrentContext } from "../../hooks/useCurrentContext"
import { cn } from "../../lib/utils"
import { useAssistantChat } from "../../services/assistantApi"
import useAppStore from "../../stores/useAppStore"
import { Button } from "../button"
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "../drop-menu"
import { Input } from "../input"
import { PersonalizationDialog } from "../PersonalizationDialog"
import { Sheet, SheetContent, SheetTrigger } from "../sheet"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../tooltip"
import { TooltipButton } from "../TooltipButton"

// Chat sidebar context
export const ChatSidebarContext = createContext(undefined)

export function ChatSidebarProvider({ children }) {
	const [isChatOpen, setIsChatOpen] = useState(false)

	const toggleChat = () => {
		setIsChatOpen((prev) => !prev)
	}

	const closeChatSidebar = () => {
		setIsChatOpen(false)
	}

	return <ChatSidebarContext value={{ isChatOpen, toggleChat, closeChatSidebar }}>{children}</ChatSidebarContext>
}

// User Avatar Menu Component
export const UserAvatarMenu = function UserAvatarMenu() {
	const { user, logout } = useAuth()
	const navigate = useNavigate()
	const [open, setOpen] = useState(false)
	const [personalizationOpen, setPersonalizationOpen] = useState(false)

	const handleLogout = async () => {
		await logout()
		navigate("/auth")
	}

	// Get user initials
	const getUserInitials = () => {
		if (!user) return "U"
		if (user.username) {
			return user.username.substring(0, 2).toUpperCase()
		}
		if (user.email) {
			const name = user.email.split("@")[0]
			return name.substring(0, 2).toUpperCase()
		}
		return "U"
	}

	return (
		<>
			<DropdownMenu open={open} onOpenChange={setOpen}>
				<TooltipProvider>
					<Tooltip>
						<TooltipTrigger asChild>
							<DropdownMenuTrigger asChild>
								<button
									type="button"
									className="flex items-center rounded-full transition-all hover:bg-muted focus:outline-none h-10 w-10 justify-center"
								>
									<div className="h-8 w-8 rounded-full bg-white flex items-center justify-center overflow-hidden border border-slate-100 shadow-sm">
										<div className="text-transparent bg-clip-text bg-gradient-to-r from-pink-500 via-orange-500 to-cyan-500 font-semibold text-sm">
											{getUserInitials()}
										</div>
									</div>
								</button>
							</DropdownMenuTrigger>
						</TooltipTrigger>
						<TooltipContent sideOffset={6}>
							<p>Profile</p>
						</TooltipContent>
					</Tooltip>
				</TooltipProvider>
				<DropdownMenuContent className="w-56" align="end" forceMount>
					<DropdownMenuLabel className="font-normal">
						<div className="flex flex-col space-y-1">
							<p className="text-sm font-medium leading-none">
								{user?.username || user?.email?.split("@")[0] || "User"}
							</p>
							<p className="text-xs leading-none text-muted-foreground">
								{user?.email || "Not logged in"}
							</p>
						</div>
					</DropdownMenuLabel>
					<DropdownMenuSeparator />
					<DropdownMenuGroup>
						<DropdownMenuItem onClick={() => navigate("/settings")}>
							<Settings className="mr-2 h-4 w-4" />
							<span>Settings</span>
						</DropdownMenuItem>
						<DropdownMenuItem onClick={() => setPersonalizationOpen(true)}>
							<Sparkles className="mr-2 h-4 w-4" />
							<span>Personalize AI</span>
						</DropdownMenuItem>
					</DropdownMenuGroup>
					<DropdownMenuSeparator />
					<DropdownMenuItem onClick={handleLogout}>
						<LogOut className="mr-2 h-4 w-4" />
						<span>Log out</span>
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			<PersonalizationDialog
				open={personalizationOpen}
				onOpenChange={setPersonalizationOpen}
			/>
		</>
	)
}

// Logo Component
export function Logo({ className, size = "md", href = "/" }) {
	const sizeClasses = {
		sm: "h-8",
		md: "h-9",
		lg: "h-10",
	}

	return (
		<Link to={href} className={cn("flex items-center gap-2", className)}>
			<div className="relative">
				<img
					src="/logo.png"
					alt="Talimio Logo"
					width={size === "sm" ? 24 : size === "md" ? 32 : 40}
					height={size === "sm" ? 24 : size === "md" ? 32 : 40}
					className={cn("object-contain", sizeClasses[size])}
				/>
			</div>
			<span
				className={cn(
					"font-bold tracking-tight text-foreground dark:text-white",
					size === "sm" ? "text-lg" : size === "md" ? "text-xl" : "text-2xl"
				)}
			>
				Tali
				<span className="text-transparent bg-clip-text bg-gradient-to-r from-pink-500 via-orange-500 to-cyan-500">
					mio
				</span>
			</span>
		</Link>
	)
}

// Chat Sidebar Component
export function ChatSidebar() {
	const { isChatOpen, toggleChat } = useChatSidebar()
	const [inputValue, setInputValue] = useState("")
	const [isLoading, setIsLoading] = useState(false)
	const messagesEndRef = useRef(null)
	const { theme } = useTheme()
	const isDarkMode = theme === "dark"
	const assistantSidebarPinned = useAppStore((state) => state.preferences.assistantSidebarPinned)
	const assistantSidebarWidth = useAppStore((state) => state.preferences.assistantSidebarWidth)
	const toggleAssistantSidebarPin = useAppStore((state) => state.toggleAssistantSidebarPin)
	const setAssistantSidebarWidth = useAppStore((state) => state.setAssistantSidebarWidth)
	const { sendMessage, sendStreamingMessage } = useAssistantChat()
	const [useStreaming, _setUseStreaming] = useState(true) // Default to streaming
	const [isResizing, setIsResizing] = useState(false)
	const [startX, setStartX] = useState(0)
	const [startWidth, setStartWidth] = useState(0)

	// Get current page context for context-aware assistance
	const currentContext = useCurrentContext()

	// Create a unique conversation key based on context
	const conversationKey = currentContext ? `${currentContext.contextType}-${currentContext.contextId}` : "general"

	// Store conversations per context
	const [conversations, setConversations] = useState({})

	// Initialize conversation for current context if it doesn't exist
	const initializeConversation = () => {
		setConversations((prev) => {
			if (!prev[conversationKey]) {
				const initialMessage = {
					id: "1",
					content: currentContext
						? `Hello! I can see you're viewing a ${currentContext.contextType}. How can I help you with this content?`
						: "Hello! I'm your learning assistant. How can I help you today?",
					role: "assistant",
					timestamp: new Date(),
				}

				return {
					...prev,
					[conversationKey]: [initialMessage],
				}
			}
			return prev
		})
	}

	// Initialize conversation when context changes
	useEffect(() => {
		initializeConversation()
	}, [initializeConversation])

	// Get current conversation
	const messages = conversations[conversationKey] || []

	const setMessages = (updateFn) => {
		setConversations((prev) => {
			const currentMessages = prev[conversationKey] || []
			const newMessages = typeof updateFn === "function" ? updateFn(currentMessages) : updateFn
			return {
				...prev,
				[conversationKey]: newMessages,
			}
		})
	}

	// Resize handlers
	const handleResizeStart = (e) => {
		e.preventDefault()
		e.stopPropagation()
		setIsResizing(true)
		setStartX(e.clientX)
		setStartWidth(assistantSidebarWidth)
		document.body.style.userSelect = "none" // Prevent text selection during resize
		document.body.style.cursor = "col-resize" // Set global cursor
	}

	const handleResizeMove = (e) => {
		if (!isResizing) return
		e.preventDefault()

		// Calculate new width (drag left to make wider, right to make narrower)
		const deltaX = startX - e.clientX
		const newWidth = startWidth + deltaX

		// Apply width with constraints (min: 300px, max: 800px)
		const clampedWidth = Math.max(300, Math.min(800, newWidth))
		setAssistantSidebarWidth(clampedWidth)
	}

	const handleResizeEnd = () => {
		if (!isResizing) return
		setIsResizing(false)
		document.body.style.userSelect = "" // Restore text selection
		document.body.style.cursor = "" // Reset global cursor
	}

	// Keyboard resize handler
	const handleKeyDown = (e) => {
		if (e.key === "ArrowLeft") {
			e.preventDefault()
			const newWidth = assistantSidebarWidth + (e.shiftKey ? 50 : 10)
			const clampedWidth = Math.max(300, Math.min(800, newWidth))
			setAssistantSidebarWidth(clampedWidth)
		} else if (e.key === "ArrowRight") {
			e.preventDefault()
			const newWidth = assistantSidebarWidth - (e.shiftKey ? 50 : 10)
			const clampedWidth = Math.max(300, Math.min(800, newWidth))
			setAssistantSidebarWidth(clampedWidth)
		}
	}

	// Add event listeners for resize
	useEffect(() => {
		if (isResizing) {
			document.addEventListener("mousemove", handleResizeMove)
			document.addEventListener("mouseup", handleResizeEnd)

			return () => {
				document.removeEventListener("mousemove", handleResizeMove)
				document.removeEventListener("mouseup", handleResizeEnd)
			}
		}
	}, [isResizing, handleResizeEnd, handleResizeMove])

	// Scroll to bottom when messages change
	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
	})

	const handleSendMessage = async () => {
		if (!inputValue.trim()) return

		// Add user message
		const userMessage = {
			id: Date.now().toString(),
			content: inputValue,
			role: "user",
			timestamp: new Date(),
		}
		setMessages((prev) => [...prev, userMessage])
		const userInput = inputValue // Save input before clearing
		setInputValue("")
		setIsLoading(true)

		try {
			// Convert messages to conversation history format
			const conversationHistory = messages.map((msg) => ({
				role: msg.role,
				content: msg.content,
			}))

			// Context is passed to assistant for relevant responses

			if (useStreaming) {
				// Add placeholder for assistant message
				const assistantMessageId = (Date.now() + 1).toString()
				const assistantMessage = {
					id: assistantMessageId,
					content: "",
					role: "assistant",
					timestamp: new Date(),
				}
				setMessages((prev) => [...prev, assistantMessage])
				setIsLoading(false) // Turn off loading immediately since we have a placeholder

				// Send streaming message with context
				await sendStreamingMessage(
					userInput,
					conversationHistory,
					(_chunk, fullResponse) => {
						// Update the assistant message with streaming content
						setMessages((prev) =>
							prev.map((msg) => (msg.id === assistantMessageId ? { ...msg, content: fullResponse } : msg))
						)
					},
					currentContext // Pass context data
				)
			} else {
				// Send regular message with context
				const response = await sendMessage(
					userInput,
					conversationHistory,
					currentContext // Pass context data
				)

				const assistantMessage = {
					id: (Date.now() + 1).toString(),
					content: response.response,
					role: "assistant",
					timestamp: new Date(),
					contextSource: response.context_source || null,
				}
				setMessages((prev) => [...prev, assistantMessage])
			}
		} catch (_error) {
			const errorMessage = {
				id: (Date.now() + 1).toString(),
				content: "Sorry, I encountered an error. Please try again.",
				role: "assistant",
				timestamp: new Date(),
			}
			setMessages((prev) => [...prev, errorMessage])
		} finally {
			setIsLoading(false)
		}
	}

	useEffect(() => {
		// Add padding to main content when sidebar is pinned and open
		if (assistantSidebarPinned && isChatOpen) {
			document.body.style.paddingRight = `${assistantSidebarWidth}px`
		} else {
			document.body.style.paddingRight = "0"
		}

		return () => {
			document.body.style.paddingRight = "0"
		}
	}, [assistantSidebarPinned, isChatOpen, assistantSidebarWidth])

	return (
		<>
			{/* Overlay when sidebar is open on mobile */}
			<AnimatePresence>
				{isChatOpen && !assistantSidebarPinned && (
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 0.5 }}
						exit={{ opacity: 0 }}
						className="fixed inset-0 bg-black z-40 md:hidden"
						onClick={toggleChat}
					/>
				)}
			</AnimatePresence>

			{/* Chat Sidebar */}
			<motion.div
				className={cn(
					"fixed top-0 right-0 z-50 h-screen shadow-xl relative",
					isDarkMode ? "bg-zinc-900 text-white" : "bg-white text-foreground",
					"border-l",
					isDarkMode ? "border-zinc-800" : "border-slate-200"
				)}
				style={{
					width: `${assistantSidebarWidth}px`,
					transition: isResizing ? "none" : "width 0.2s ease-out",
				}}
				initial={{ x: "100%" }}
				animate={{
					x: isChatOpen ? 0 : "100%",
					position: assistantSidebarPinned && isChatOpen ? "fixed" : "fixed",
					boxShadow: assistantSidebarPinned && isChatOpen ? "none" : "-4px 0 15px rgba(0, 0, 0, 0.1)",
				}}
				transition={{ type: "spring", damping: 20, stiffness: 300 }}
			>
				{/* Resize Handle */}
				<div
					role="slider"
					aria-orientation="vertical"
					aria-label="Resize sidebar width"
					aria-valuemin={300}
					aria-valuemax={800}
					aria-valuenow={assistantSidebarWidth}
					tabIndex={0}
					className={cn(
						"absolute left-0 top-0 bottom-0 w-3 cursor-col-resize z-10 group",
						"hover:bg-blue-500/50 transition-colors duration-150",
						"active:bg-blue-600/70 focus:outline-none focus:ring-2 focus:ring-blue-500",
						isDarkMode ? "bg-zinc-700/30" : "bg-slate-300/30",
						isResizing && "bg-blue-500/70"
					)}
					onMouseDown={handleResizeStart}
					onKeyDown={handleKeyDown}
					style={{
						touchAction: "none", // Prevent touch scrolling
					}}
					title="Drag to resize sidebar (Arrow keys to resize, Shift+Arrow for larger steps)"
				>
					<div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
						<GripVertical
							className={cn(
								"h-5 w-5 transition-opacity duration-150",
								isDarkMode ? "text-zinc-400" : "text-slate-500",
								"group-hover:opacity-100",
								isResizing ? "opacity-100" : "opacity-50"
							)}
						/>
					</div>
				</div>
				{/* Header */}
				<div
					className={cn(
						"flex items-center justify-between p-4 border-b",
						isDarkMode ? "border-zinc-800" : "border-slate-200"
					)}
				>
					<div className="flex items-center gap-2">
						<Bot className={cn("h-5 w-5", isDarkMode ? "text-emerald-400" : "text-emerald-600")} />
						<h2 className="font-semibold">Learning Assistant</h2>
					</div>
					<div className="flex items-center gap-2">
						<Button
							variant="ghost"
							size="icon"
							onClick={toggleAssistantSidebarPin}
							className={cn(
								isDarkMode ? "text-zinc-400 hover:text-white" : "text-muted-foreground hover:text-foreground"
							)}
						>
							{assistantSidebarPinned ? <PinOff className="h-5 w-5" /> : <Pin className="h-5 w-5" />}
							<span className="sr-only">{assistantSidebarPinned ? "Unpin Chat" : "Pin Chat"}</span>
						</Button>
						<Button
							variant="ghost"
							size="icon"
							onClick={toggleChat}
							className={cn(
								isDarkMode ? "text-zinc-400 hover:text-white" : "text-muted-foreground hover:text-foreground"
							)}
						>
							<X className="h-5 w-5" />
							<span className="sr-only">Close</span>
						</Button>
					</div>
				</div>

				{/* Messages */}
				<div className="flex flex-col h-[calc(100vh-8rem)] overflow-y-auto p-4">
					{messages.map((message) => (
						<div
							key={message.id}
							className={cn(
								"mb-4 max-w-[85%] rounded-lg p-3",
								message.role === "user"
									? "ml-auto bg-primary text-primary-foreground"
									: isDarkMode
										? "bg-zinc-800"
										: "bg-slate-100"
							)}
						>
							<p className="text-sm">{message.content}</p>
							{/* Show context source for assistant messages */}
							{message.role === "assistant" && message.contextSource && (
								<div
									className={cn(
										"text-xs mt-2 pt-2 border-t opacity-70",
										isDarkMode ? "border-zinc-700 text-zinc-400" : "border-slate-200 text-slate-500"
									)}
								>
									📄 Context: {message.contextSource}
								</div>
							)}
						</div>
					))}
					{isLoading && (
						<div className={cn("mb-4 max-w-[85%] rounded-lg p-3", isDarkMode ? "bg-zinc-800" : "bg-slate-100")}>
							<div className="flex gap-1">
								<div className="h-2 w-2 rounded-full bg-current animate-bounce" />
								<div className="h-2 w-2 rounded-full bg-current animate-bounce delay-75" />
								<div className="h-2 w-2 rounded-full bg-current animate-bounce delay-150" />
							</div>
						</div>
					)}
					<div ref={messagesEndRef} />
				</div>

				{/* Input */}
				<div
					className={cn(
						"absolute bottom-0 left-0 right-0 p-4 border-t",
						isDarkMode ? "border-zinc-800" : "border-slate-200"
					)}
				>
					<div className="relative w-full rounded-lg border bg-background shadow-sm">
						<Input
							value={inputValue}
							onChange={(e) => setInputValue(e.target.value)}
							placeholder="Ask a follow up..."
							className={cn(
								"border-0 focus-visible:ring-0 focus-visible:ring-offset-0 pr-24",
								isDarkMode ? "bg-zinc-800" : "bg-white"
							)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault()
									handleSendMessage()
								}
							}}
						/>
						<div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
							<Button variant="ghost" size="icon" className="h-8 w-8 rounded-full" onClick={() => {}}>
								<Paperclip className="h-4 w-4" />
								<span className="sr-only">Attach file</span>
							</Button>
							<Button variant="ghost" size="icon" className="h-8 w-8 rounded-full" onClick={() => {}}>
								<Mic className="h-4 w-4" />
								<span className="sr-only">Voice input</span>
							</Button>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 rounded-full"
								onClick={handleSendMessage}
								disabled={!inputValue.trim() || isLoading}
							>
								<Send className="h-4 w-4" />
								<span className="sr-only">Send</span>
							</Button>
						</div>
					</div>
				</div>
			</motion.div>
		</>
	)
}

// Main Header Component
export function MainHeader({ transparent = false, className }) {
	const [scrolled, setScrolled] = useState(false)
	const [searchOpen, setSearchOpen] = useState(false)
	const [searchQuery, setSearchQuery] = useState("")
	const { toggleChat } = useChatSidebar()

	// Handle scroll effect
	useEffect(() => {
		const handleScroll = () => {
			setScrolled(window.scrollY > 10)
		}
		window.addEventListener("scroll", handleScroll)
		return () => window.removeEventListener("scroll", handleScroll)
	}, [])

	// Determine header background style based on scroll and transparent prop
	const headerBg = transparent ? (scrolled ? "bg-white/95 backdrop-blur-md shadow-sm" : "bg-transparent") : "bg-white"

	return (
		<header className={cn("fixed top-0 left-0 right-0 z-50 transition-all duration-300", headerBg, className)}>
			<div className="container mx-auto px-4">
				<div className="flex h-16 items-center justify-between">
					{/* Logo */}
					<Logo />

					{/* Center section - can be used for navigation or search */}
					<div className="flex-1 flex justify-center">
						{searchOpen && (
							<motion.div
								initial={{ width: 40, opacity: 0 }}
								animate={{ width: 320, opacity: 1 }}
								exit={{ width: 40, opacity: 0 }}
								transition={{ duration: 0.2 }}
								className="relative max-w-md w-full"
							>
								<Input
									type="text"
									placeholder="Search..."
									className="pr-8"
									value={searchQuery}
									onChange={(e) => setSearchQuery(e.target.value)}
									autoFocus
								/>
								<button
									type="button"
									onClick={() => setSearchOpen(false)}
									className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground"
								>
									<X className="h-4 w-4" />
								</button>
							</motion.div>
						)}
					</div>

					{/* Right Section - Actions and User */}
					<div className="flex items-center">
						{/* Action buttons with consistent styling */}
						<div className="flex items-center gap-1 mr-1">
							{!searchOpen && (
								<TooltipButton
									variant="ghost"
									size="icon"
									onClick={() => setSearchOpen(true)}
									className="h-10 w-10 rounded-full text-muted-foreground hover:bg-muted transition-all"
									tooltipContent="Search"
								>
									<Search className="h-5 w-5" />
								</TooltipButton>
							)}

							<TooltipButton
								variant="ghost"
								size="icon"
								onClick={toggleChat}
								className="h-10 w-10 rounded-full text-muted-foreground hover:bg-muted transition-all"
								tooltipContent="Chat with AI"
								tooltipSide="bottom"
							>
								<MessageSquare className="h-5 w-5" />
							</TooltipButton>
						</div>

						{/* User Avatar Menu */}
						<UserAvatarMenu />

						{/* Mobile Menu */}
						<Sheet>
							<SheetTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className="md:hidden h-10 w-10 rounded-full text-muted-foreground hover:bg-muted ml-1"
								>
									<Menu className="h-5 w-5" />
									<span className="sr-only">Toggle menu</span>
								</Button>
							</SheetTrigger>
							<SheetContent side="right" className="w-[300px] sm:w-[400px]">
								<div className="flex flex-col h-full">
									<div className="py-6">
										<Logo size="sm" className="mx-auto" />
									</div>
									<nav className="flex flex-col space-y-4">
										<Link
											to="/courses"
											className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-muted transition-colors"
										>
											<BookOpen className="h-5 w-5 text-course" />
											<span className="font-medium">Courses</span>
										</Link>
										<Link
											to="/books"
											className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-muted transition-colors"
										>
											<FileText className="h-5 w-5 text-book" />
											<span className="font-medium">Books</span>
										</Link>
										<Link
											to="/videos"
											className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-muted transition-colors"
										>
											<Youtube className="h-5 w-5 text-video" />
											<span className="font-medium">Videos</span>
										</Link>
										<Link
											to="/flashcards"
											className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-muted transition-colors"
										>
											<Layers className="h-5 w-5 text-flashcard" />
											<span className="font-medium">Flashcards</span>
										</Link>
										<div className="px-4 py-3">
											<Button onClick={toggleChat} className="w-full flex items-center justify-center gap-2">
												<MessageSquare className="h-5 w-5" />
												<span>Open Chat Assistant</span>
											</Button>
										</div>
									</nav>
									<div className="mt-auto pt-6 border-t">
										<Button className="w-full" variant="outline">
											<Sparkles className="mr-2 h-4 w-4" />
											Generate Course
										</Button>
									</div>
								</div>
							</SheetContent>
						</Sheet>
					</div>
				</div>
			</div>
		</header>
	)
}

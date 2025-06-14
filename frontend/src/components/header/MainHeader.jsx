import { AnimatePresence, motion } from "framer-motion";
import {
	BookOpen,
	Bot,
	FileText,
	HelpCircle,
	Layers,
	LogOut,
	Menu,
	MessageSquare,
	Mic,
	Moon,
	Paperclip,
	Pin,
	PinOff,
	Search,
	Send,
	Settings,
	Sparkles,
	Sun,
	User,
	X,
	Youtube,
} from "lucide-react";
import React, {
	useState,
	useEffect,
	useRef,
	createContext,
	useContext,
} from "react";
import { Link } from "react-router-dom";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../lib/utils";
import { useAssistantChat } from "../../services/assistantApi";
import { Button } from "../button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "../drop-menu";
import { Input } from "../input";
import { Sheet, SheetContent, SheetTrigger } from "../sheet";
import { Switch } from "../switch";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "../tooltip";

// Chat sidebar context
const ChatSidebarContext = createContext(undefined);

export function ChatSidebarProvider({ children }) {
	const [isChatOpen, setIsChatOpen] = useState(false);

	const toggleChat = () => {
		setIsChatOpen((prev) => !prev);
	};

	const closeChatSidebar = () => {
		setIsChatOpen(false);
	};

	return (
		<ChatSidebarContext.Provider
			value={{ isChatOpen, toggleChat, closeChatSidebar }}
		>
			{children}
		</ChatSidebarContext.Provider>
	);
}

export function useChatSidebar() {
	const context = useContext(ChatSidebarContext);
	if (context === undefined) {
		throw new Error("useChatSidebar must be used within a ChatSidebarProvider");
	}
	return context;
}

// User Avatar Menu Component
export function UserAvatarMenu() {
	const { theme, setTheme } = useTheme();
	const [open, setOpen] = useState(false);

	return (
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
										JD
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
						<p className="text-sm font-medium leading-none">John Doe</p>
						<p className="text-xs leading-none text-muted-foreground">
							john.doe@example.com
						</p>
					</div>
				</DropdownMenuLabel>
				<DropdownMenuSeparator />
				<DropdownMenuGroup>
					<DropdownMenuItem>
						<User className="mr-2 h-4 w-4" />
						<span>Profile</span>
					</DropdownMenuItem>
					<DropdownMenuItem>
						<BookOpen className="mr-2 h-4 w-4" />
						<span>My Library</span>
					</DropdownMenuItem>
					<DropdownMenuItem>
						<MessageSquare className="mr-2 h-4 w-4" />
						<span>Notifications</span>
					</DropdownMenuItem>
					<DropdownMenuItem>
						<Settings className="mr-2 h-4 w-4" />
						<span>Settings</span>
					</DropdownMenuItem>
				</DropdownMenuGroup>
				<DropdownMenuSeparator />
				<DropdownMenuItem className="flex items-center justify-between">
					<div className="flex items-center">
						{theme === "dark" ? (
							<Moon className="mr-2 h-4 w-4" />
						) : (
							<Sun className="mr-2 h-4 w-4" />
						)}
						<span>Dark Mode</span>
					</div>
					<Switch
						checked={theme === "dark"}
						onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
					/>
				</DropdownMenuItem>
				<DropdownMenuItem>
					<HelpCircle className="mr-2 h-4 w-4" />
					<span>Help & Support</span>
				</DropdownMenuItem>
				<DropdownMenuSeparator />
				<DropdownMenuItem className="text-destructive focus:text-destructive">
					<LogOut className="mr-2 h-4 w-4" />
					<span>Log out</span>
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

// Logo Component
export function Logo({ className, size = "md", href = "/" }) {
	const sizeClasses = {
		sm: "h-8",
		md: "h-9",
		lg: "h-10",
	};

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
					size === "sm" ? "text-lg" : size === "md" ? "text-xl" : "text-2xl",
				)}
			>
				Tali
				<span className="text-transparent bg-clip-text bg-gradient-to-r from-pink-500 via-orange-500 to-cyan-500">
					mio
				</span>
			</span>
		</Link>
	);
}

// Chat Sidebar Component
export function ChatSidebar() {
	const { isChatOpen, toggleChat } = useChatSidebar();
	const [messages, setMessages] = useState([
		{
			id: "1",
			content: "Hello! I'm your learning assistant. How can I help you today?",
			role: "assistant",
			timestamp: new Date(),
		},
	]);
	const [inputValue, setInputValue] = useState("");
	const [isLoading, setIsLoading] = useState(false);
	const messagesEndRef = useRef(null);
	const { theme } = useTheme();
	const isDarkMode = theme === "dark";
	const [isPinned, setIsPinned] = useState(false);
	const { sendMessage } = useAssistantChat();

	// Scroll to bottom when messages change
	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	});

	const handleSendMessage = async () => {
		if (!inputValue.trim()) return;

		// Add user message
		const userMessage = {
			id: Date.now().toString(),
			content: inputValue,
			role: "user",
			timestamp: new Date(),
		};
		setMessages((prev) => [...prev, userMessage]);
		setInputValue("");
		setIsLoading(true);

		try {
			// Convert messages to conversation history format
			const conversationHistory = messages.map((msg) => ({
				role: msg.role,
				content: msg.content,
			}));
			conversationHistory.push({ role: "user", content: inputValue });

			// Send message to API
			const response = await sendMessage(inputValue, conversationHistory);

			const assistantMessage = {
				id: (Date.now() + 1).toString(),
				content: response.response,
				role: "assistant",
				timestamp: new Date(),
			};
			setMessages((prev) => [...prev, assistantMessage]);
		} catch (error) {
			console.error("Failed to send message:", error);
			const errorMessage = {
				id: (Date.now() + 1).toString(),
				content: "Sorry, I encountered an error. Please try again.",
				role: "assistant",
				timestamp: new Date(),
			};
			setMessages((prev) => [...prev, errorMessage]);
		} finally {
			setIsLoading(false);
		}
	};

	useEffect(() => {
		// Add padding to main content when sidebar is pinned and open
		if (isPinned && isChatOpen) {
			document.body.style.paddingRight = "384px"; // 96 * 4 = 384px (for md:w-96)
		} else {
			document.body.style.paddingRight = "0";
		}

		return () => {
			document.body.style.paddingRight = "0";
		};
	}, [isPinned, isChatOpen]);

	return (
		<>
			{/* Overlay when sidebar is open on mobile */}
			<AnimatePresence>
				{isChatOpen && !isPinned && (
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
					"fixed top-0 right-0 z-50 h-screen shadow-xl",
					isDarkMode ? "bg-zinc-900 text-white" : "bg-white text-foreground",
					"border-l",
					isDarkMode ? "border-zinc-800" : "border-slate-200",
					isPinned ? "w-80 md:w-96" : "w-80 md:w-96",
				)}
				initial={{ x: "100%" }}
				animate={{
					x: isChatOpen ? 0 : "100%",
					position: isPinned && isChatOpen ? "fixed" : "fixed",
					boxShadow:
						isPinned && isChatOpen ? "none" : "-4px 0 15px rgba(0, 0, 0, 0.1)",
				}}
				transition={{ type: "spring", damping: 20, stiffness: 300 }}
			>
				{/* Header */}
				<div
					className={cn(
						"flex items-center justify-between p-4 border-b",
						isDarkMode ? "border-zinc-800" : "border-slate-200",
					)}
				>
					<div className="flex items-center gap-2">
						<Bot
							className={cn(
								"h-5 w-5",
								isDarkMode ? "text-emerald-400" : "text-emerald-600",
							)}
						/>
						<h2 className="font-semibold">Learning Assistant</h2>
					</div>
					<div className="flex items-center gap-2">
						<Button
							variant="ghost"
							size="icon"
							onClick={() => setIsPinned(!isPinned)}
							className={cn(
								isDarkMode
									? "text-zinc-400 hover:text-white"
									: "text-muted-foreground hover:text-foreground",
							)}
						>
							{isPinned ? (
								<PinOff className="h-5 w-5" />
							) : (
								<Pin className="h-5 w-5" />
							)}
							<span className="sr-only">
								{isPinned ? "Unpin Chat" : "Pin Chat"}
							</span>
						</Button>
						<Button
							variant="ghost"
							size="icon"
							onClick={toggleChat}
							className={cn(
								isDarkMode
									? "text-zinc-400 hover:text-white"
									: "text-muted-foreground hover:text-foreground",
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
										: "bg-slate-100",
							)}
						>
							<div className="flex items-center gap-2 mb-1">
								{message.role === "assistant" ? (
									<Bot className="h-4 w-4" />
								) : (
									<User className="h-4 w-4" />
								)}
								<span className="text-xs opacity-70">
									{message.role === "assistant" ? "Assistant" : "You"}
								</span>
							</div>
							<p className="text-sm">{message.content}</p>
						</div>
					))}
					{isLoading && (
						<div
							className={cn(
								"mb-4 max-w-[85%] rounded-lg p-3",
								isDarkMode ? "bg-zinc-800" : "bg-slate-100",
							)}
						>
							<div className="flex items-center gap-2 mb-1">
								<Bot className="h-4 w-4" />
								<span className="text-xs opacity-70">Assistant</span>
							</div>
							<div className="flex gap-1 mt-2">
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
						isDarkMode ? "border-zinc-800" : "border-slate-200",
					)}
				>
					<div className="relative w-full rounded-lg border bg-background shadow-sm">
						<Input
							value={inputValue}
							onChange={(e) => setInputValue(e.target.value)}
							placeholder="Ask a follow up..."
							className={cn(
								"border-0 focus-visible:ring-0 focus-visible:ring-offset-0 pr-24",
								isDarkMode ? "bg-zinc-800" : "bg-white",
							)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault();
									handleSendMessage();
								}
							}}
						/>
						<div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 rounded-full"
								onClick={() => {}}
							>
								<Paperclip className="h-4 w-4" />
								<span className="sr-only">Attach file</span>
							</Button>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 rounded-full"
								onClick={() => {}}
							>
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
	);
}

// Main Header Component
export function MainHeader({ transparent = false, className }) {
	const [scrolled, setScrolled] = useState(false);
	const [searchOpen, setSearchOpen] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const { toggleChat } = useChatSidebar();

	// Handle scroll effect
	useEffect(() => {
		const handleScroll = () => {
			setScrolled(window.scrollY > 10);
		};
		window.addEventListener("scroll", handleScroll);
		return () => window.removeEventListener("scroll", handleScroll);
	}, []);

	// Determine header background style based on scroll and transparent prop
	const headerBg = transparent
		? scrolled
			? "bg-white/95 backdrop-blur-md shadow-sm"
			: "bg-transparent"
		: "bg-white";

	return (
		<header
			className={cn(
				"fixed top-0 left-0 right-0 z-50 transition-all duration-300",
				headerBg,
				className,
			)}
		>
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
								<TooltipProvider delayDuration={300}>
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												onClick={() => setSearchOpen(true)}
												className="h-10 w-10 rounded-full text-muted-foreground hover:bg-muted transition-all"
											>
												<Search className="h-5 w-5" />
											</Button>
										</TooltipTrigger>
										<TooltipContent sideOffset={6}>
											<p>Search</p>
										</TooltipContent>
									</Tooltip>
								</TooltipProvider>
							)}

							<TooltipProvider delayDuration={300}>
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											onClick={toggleChat}
											className="h-10 w-10 rounded-full text-muted-foreground hover:bg-muted transition-all"
										>
											<MessageSquare className="h-5 w-5" />
										</Button>
									</TooltipTrigger>
									<TooltipContent sideOffset={6}>
										<p>Chat with AI</p>
									</TooltipContent>
								</Tooltip>
							</TooltipProvider>
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
											<Button
												onClick={toggleChat}
												className="w-full flex items-center justify-center gap-2"
											>
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
	);
}

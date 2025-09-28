import { motion } from "framer-motion"
import {
	BookOpen,
	FileText,
	LogOut,
	Menu,
	MessageSquare,
	Monitor,
	Moon,
	Search,
	Settings,
	Sparkles,
	Sun,
	X,
	Youtube,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "../../contexts/ThemeContext"
import { cn } from "../../lib/utils"
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
import { TooltipButton } from "../TooltipButton"

// User Avatar Menu Component
/**
 * @returns {JSX.Element}
 */
export function UserAvatarMenu() {
	const { user, logout } = useAuth()
	const navigate = useNavigate()
	const [open, setOpen] = useState(false)
	const [personalizationOpen, setPersonalizationOpen] = useState(false)
	const { theme, setTheme } = useTheme()

	const handleLogout = useCallback(async () => {
		await logout()
		navigate("/auth")
	}, [logout, navigate])

	// Get user initials - memoized to prevent recalculation
	const userInitials = useMemo(() => {
		if (!user) return "U"
		if (user.username) {
			return user.username.substring(0, 2).toUpperCase()
		}
		if (user.email) {
			const name = user.email.split("@")[0]
			return name.substring(0, 2).toUpperCase()
		}
		return "U"
	}, [user])

	return (
		<>
			<DropdownMenu open={open} onOpenChange={setOpen}>
				<DropdownMenuTrigger asChild>
					<TooltipButton
						variant="ghost"
						size="icon"
						className="h-10 w-10 rounded-full hover:bg-gray-100 transition-all p-0"
						tooltipContent="Profile"
						tooltipSide="bottom"
						asChild
					>
						<button type="button" className="flex items-center justify-center">
							<div className="h-8 w-8 rounded-full bg-white flex items-center justify-center overflow-hidden border border-slate-100 shadow-sm">
								<div className="text-transparent bg-clip-text bg-gradient-to-r from-pink-500 via-orange-500 to-cyan-500 font-semibold text-sm">
									{userInitials}
								</div>
							</div>
						</button>
					</TooltipButton>
				</DropdownMenuTrigger>
				<DropdownMenuContent className="w-56 border-gray-200" align="end" forceMount>
					<DropdownMenuLabel className="font-normal">
						<div className="flex flex-col space-y-1">
							<p className="text-sm font-medium leading-none">
								{user?.username || user?.email?.split("@")[0] || "User"}
							</p>
							<p className="text-xs leading-none text-gray-100-foreground">{user?.email || "Not logged in"}</p>
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
					<DropdownMenuGroup>
						<div className="px-2 py-1.5">
							<div className="flex items-center justify-between">
								<span className="text-sm">Theme</span>
								<div className="flex items-center gap-1 rounded-md border bg-gray-100 p-1">
									<button
										type="button"
										onClick={() => setTheme("light")}
										className={cn(
											"inline-flex items-center justify-center rounded-sm px-2 py-1 text-xs font-medium transition-colors",
											theme === "light"
												? "bg-white text-gray-900 shadow-sm"
												: "text-gray-100-foreground hover:text-gray-900"
										)}
										aria-label="Light theme"
									>
										<Sun className="h-3 w-3" />
									</button>
									<button
										type="button"
										onClick={() => setTheme("dark")}
										className={cn(
											"inline-flex items-center justify-center rounded-sm px-2 py-1 text-xs font-medium transition-colors",
											theme === "dark"
												? "bg-white text-gray-900 shadow-sm"
												: "text-gray-100-foreground hover:text-gray-900"
										)}
										aria-label="Dark theme"
									>
										<Moon className="h-3 w-3" />
									</button>
									<button
										type="button"
										onClick={() => setTheme("system")}
										className={cn(
											"inline-flex items-center justify-center rounded-sm px-2 py-1 text-xs font-medium transition-colors",
											theme === "system"
												? "bg-white text-gray-900 shadow-sm"
												: "text-gray-100-foreground hover:text-gray-900"
										)}
										aria-label="System theme"
									>
										<Monitor className="h-3 w-3" />
									</button>
								</div>
							</div>
						</div>
					</DropdownMenuGroup>
					<DropdownMenuSeparator />
					<DropdownMenuItem onClick={handleLogout}>
						<LogOut className="mr-2 h-4 w-4" />
						<span>Log out</span>
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			<PersonalizationDialog open={personalizationOpen} onOpenChange={setPersonalizationOpen} />
		</>
	)
}

// Logo Component
/**
 * @param {Object} props
 * @param {string} [props.className]
 * @param {"sm" | "md" | "lg"} [props.size="md"]
 * @param {string} [props.href="/"]
 * @returns {JSX.Element}
 */
export function Logo({ className, size = "md", href = "/" }) {
	const sizeClasses = {
		sm: "h-8",
		md: "h-9",
		lg: "h-10",
	}

	// Compute size values to avoid nested ternaries
	const imageDimensions = useMemo(() => {
		if (size === "sm") return 24
		if (size === "md") return 32
		return 40
	}, [size])

	const textSize = useMemo(() => {
		if (size === "sm") return "text-lg"
		if (size === "md") return "text-xl"
		return "text-2xl"
	}, [size])

	return (
		<Link to={href} className={cn("flex items-center gap-2", className)}>
			<div className="relative">
				<img
					src="/logo.png"
					alt="Talimio Logo"
					width={imageDimensions}
					height={imageDimensions}
					className={cn("object-contain", sizeClasses[size])}
				/>
			</div>
			<span className={cn("font-bold tracking-tight text-gray-900 dark:text-white", textSize)}>
				Tali
				<span className="text-transparent bg-clip-text bg-gradient-to-r from-pink-500 via-orange-500 to-cyan-500">
					mio
				</span>
			</span>
		</Link>
	)
}

// Main Header Component
/**
 * @param {Object} props
 * @param {boolean} [props.transparent=false]
 * @param {string} [props.className]
 * @returns {JSX.Element}
 */
export function MainHeader({ transparent = false, className }) {
	const [scrolled, setScrolled] = useState(false)
	const [searchOpen, setSearchOpen] = useState(false)
	const [searchQuery, setSearchQuery] = useState("")

	// Open assistant by dispatching event
	const toggleChat = () => {
		window.dispatchEvent(new CustomEvent("openAssistant"))
	}

	// Handle scroll effect
	useEffect(() => {
		const handleScroll = () => {
			setScrolled(window.scrollY > 10)
		}
		window.addEventListener("scroll", handleScroll)
		return () => window.removeEventListener("scroll", handleScroll)
	}, [])

	// Determine header background style based on scroll and transparent prop
	const headerBg = useMemo(() => {
		if (!transparent) return "bg-white"
		return scrolled ? "bg-white/95 backdrop-blur-md shadow-sm" : "bg-transparent"
	}, [transparent, scrolled])

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
									className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-100-foreground hover:text-gray-100-foreground"
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
									className="h-10 w-10 rounded-full text-gray-100-foreground hover:bg-gray-100 transition-all"
									tooltipContent="Search"
								>
									<Search className="h-5 w-5" />
								</TooltipButton>
							)}

							<TooltipButton
								variant="ghost"
								size="icon"
								onClick={toggleChat}
								className="h-10 w-10 rounded-full text-gray-100-foreground hover:bg-gray-100 transition-all"
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
									className="md:hidden h-10 w-10 rounded-full text-gray-100-foreground hover:bg-gray-100 ml-1"
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
											className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-gray-100 transition-colors"
										>
											<BookOpen className="h-5 w-5 text-course" />
											<span className="font-medium">Courses</span>
										</Link>
										<Link
											to="/books"
											className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-gray-100 transition-colors"
										>
											<FileText className="h-5 w-5 text-book" />
											<span className="font-medium">Books</span>
										</Link>
										<Link
											to="/videos"
											className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-gray-100 transition-colors"
										>
											<Youtube className="h-5 w-5 text-video" />
											<span className="font-medium">Videos</span>
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

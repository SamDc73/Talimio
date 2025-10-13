import { AssistantRuntimeProvider } from "@assistant-ui/react"
import { AnimatePresence, motion, useDragControls } from "framer-motion"
import { GripVertical, Pin, X } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react"
import ErrorBoundary from "@/components/ErrorBoundary"
import { Button } from "@/components/Button"
import { AssistantThread } from "@/features/assistant/components/AssistantThread"
import {
	useAssistantPinned,
	useAssistantSidebarWidth,
	useSetAssistantSidebarWidth,
	useToggleAssistantPinned,
} from "@/features/assistant/hooks/assistant-store"
import { cn } from "@/lib/utils"
import { useAssistantRuntime } from "../hooks/useAssistantRuntime"

const MIN_WIDTH = 320
const MAX_WIDTH = 600
const DEFAULT_WIDTH = 400

export function ChatSidebar({ isOpen, onToggle, onClose }) {
	const assistantSidebarPinned = useAssistantPinned()
	const assistantSidebarWidth = useAssistantSidebarWidth()
	const toggleAssistantSidebarPin = useToggleAssistantPinned()
	const setAssistantSidebarWidth = useSetAssistantSidebarWidth()

	const runtime = useAssistantRuntime()
	const sidebarRef = useRef(null)
	const [isPending, startTransition] = useTransition()
	const [localWidth, setLocalWidth] = useState(assistantSidebarWidth || DEFAULT_WIDTH)

	// Auto-hide state
	const autoHideTimerRef = useRef(null)
	const [isInteracting, setIsInteracting] = useState(false)

	// Responsive design
	const [isMobile, setIsMobile] = useState(false)

	// Drag controls for resize
	const dragControls = useDragControls()

	// Check if mobile
	useEffect(() => {
		const checkMobile = () => {
			setIsMobile(window.innerWidth < 1200)
		}
		checkMobile()
		window.addEventListener("resize", checkMobile)
		return () => window.removeEventListener("resize", checkMobile)
	}, [])

	// Listen for open assistant event
	useEffect(() => {
		const handleOpenAssistant = () => {
			onToggle()
		}
		window.addEventListener("openAssistant", handleOpenAssistant)
		return () => window.removeEventListener("openAssistant", handleOpenAssistant)
	}, [onToggle])

	// Handle resize
	const handleResize = useCallback((_event, info) => {
		const newWidth = window.innerWidth - info.point.x
		const clampedWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth))
		setLocalWidth(clampedWidth)
	}, [])

	// Save width on drag end
	const handleResizeEnd = useCallback(() => {
		startTransition(() => {
			setAssistantSidebarWidth(localWidth)
		})
	}, [localWidth, setAssistantSidebarWidth])

	// Auto-hide functionality
	useEffect(() => {
		if (assistantSidebarPinned || !isOpen || isInteracting || isMobile) {
			if (autoHideTimerRef.current) {
				clearTimeout(autoHideTimerRef.current)
				autoHideTimerRef.current = null
			}
			return
		}

		const timer = setTimeout(() => {
			onClose()
		}, 30000) // 30 seconds

		autoHideTimerRef.current = timer

		return () => {
			if (timer) clearTimeout(timer)
			if (autoHideTimerRef.current === timer) {
				autoHideTimerRef.current = null
			}
		}
	}, [assistantSidebarPinned, isOpen, isInteracting, isMobile, onClose])

	// Handle body padding for pinned mode
	useEffect(() => {
		if (assistantSidebarPinned && isOpen && !isMobile) {
			document.body.style.paddingRight = `${localWidth}px`
			document.body.style.transition = "padding-right 0.3s ease"
		} else {
			document.body.style.paddingRight = "0"
		}

		return () => {
			document.body.style.paddingRight = "0"
		}
	}, [assistantSidebarPinned, isOpen, localWidth, isMobile])

	// Focus only; text is injected in AssistantThread via composer runtime
	useEffect(() => {
		const input = document.querySelector(".aui-composer-input")
		if (isOpen) input?.focus()
		else input?.blur()
	}, [isOpen])

	// Toggle pin with transition
	const handleTogglePin = useCallback(() => {
		startTransition(() => {
			toggleAssistantSidebarPin()
		})
	}, [toggleAssistantSidebarPin])

	const sidebarVariants = useMemo(
		() => ({
			open: {
				x: 0,
				opacity: 1,
				transition: {
					type: "spring",
					stiffness: 400,
					damping: 40,
				},
			},
			closed: {
				x: "100%",
				opacity: 0,
				transition: {
					type: "spring",
					stiffness: 400,
					damping: 40,
				},
			},
		}),
		[]
	)

	const overlayVariants = useMemo(
		() => ({
			open: { opacity: 0.3 },
			closed: { opacity: 0 },
		}),
		[]
	)

	return (
		<>
			{/* Backdrop overlay for unpinned mode */}
			<AnimatePresence>
				{isOpen && !assistantSidebarPinned && (
					<motion.div
						initial="closed"
						animate="open"
						exit="closed"
						variants={overlayVariants}
						className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
						onClick={onClose}
						transition={{ duration: 0.2 }}
					/>
				)}
			</AnimatePresence>

			{/* Sidebar */}
			<motion.aside
				ref={sidebarRef}
				className={cn(
					"fixed top-0 right-0 z-50 h-screen bg-background",
					"border-l border-border shadow-2xl",
					assistantSidebarPinned && "shadow-lg"
				)}
				style={{ width: `${localWidth}px` }}
				initial={false}
				animate={isOpen ? "open" : "closed"}
				variants={sidebarVariants}
				onMouseEnter={() => setIsInteracting(true)}
				onMouseLeave={() => setIsInteracting(false)}
			>
				{/* Resize handle */}
				{assistantSidebarPinned && !isMobile && (
					<motion.div
						className={cn(
							"absolute left-0 top-0 w-1.5 h-full cursor-col-resize",
							"bg-transparent hover:bg-primary/20 active:bg-primary/30",
							"transition-colors duration-200",
							"flex items-center justify-center"
						)}
						drag="x"
						dragControls={dragControls}
						dragMomentum={false}
						dragElastic={0}
						onDrag={handleResize}
						onDragEnd={handleResizeEnd}
						whileHover={{ width: 12 }}
						whileDrag={{ width: 12, backgroundColor: "rgb(var(--primary) / 0.3)" }}
					>
						<GripVertical className="h-8 w-3 opacity-0 hover:opacity-50" />
					</motion.div>
				)}

				{/* Content container with header */}
				<div className="flex h-full flex-col">
					{/* Header with controls */}
					<div className="flex items-center justify-end gap-1.5 px-3 py-2 border-b border-border/40">
						{/* Pin button */}
						{!isMobile && (
							<motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
								<Button
									variant="ghost"
									size="icon"
									onClick={handleTogglePin}
									disabled={isPending}
									className={cn(
										"h-8 w-8 rounded-md transition-all duration-200",
										assistantSidebarPinned ? "bg-primary/10 hover:bg-primary/20 text-primary" : "hover:bg-muted"
									)}
									aria-label={assistantSidebarPinned ? "Unpin sidebar" : "Pin sidebar"}
								>
									<Pin
										className={cn(
											"h-3.5 w-3.5 transition-transform duration-200",
											assistantSidebarPinned && "rotate-45"
										)}
									/>
								</Button>
							</motion.div>
						)}

						{/* Close button */}
						<motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
							<Button
								variant="ghost"
								size="icon"
								onClick={onClose}
								className="h-8 w-8 rounded-md hover:bg-muted"
								aria-label="Close assistant"
							>
								<X className="h-3.5 w-3.5" />
							</Button>
						</motion.div>
					</div>

					{/* Assistant content */}
					<div className="flex-1 overflow-hidden">
						<ErrorBoundary>
							<AssistantRuntimeProvider runtime={runtime}>
								<AssistantThread />
							</AssistantRuntimeProvider>
						</ErrorBoundary>
					</div>
				</div>
			</motion.aside>

			{/* Edge hint when closed */}
			<AnimatePresence>
				{!isOpen && !assistantSidebarPinned && (
					<motion.button
						initial={{ opacity: 0, x: 20 }}
						animate={{ opacity: 1, x: 0 }}
						exit={{ opacity: 0, x: 20 }}
						transition={{ delay: 0.5, duration: 0.3 }}
						className={cn(
							"fixed right-0 top-1/2 -translate-y-1/2",
							"w-1.5 h-24 bg-primary/20 hover:bg-primary/30",
							"rounded-l-full cursor-pointer z-30",
							"transition-all duration-200 hover:w-3"
						)}
						onClick={onToggle}
						aria-label="Open assistant"
					/>
				)}
			</AnimatePresence>
		</>
	)
}

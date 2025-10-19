import { Sparkles } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useChatSidebar } from "@/features/assistant/contexts/chatSidebarContext"

/**
 * Minimal floating toolbar that appears near selected text.
 * Prefers a custom zone handler if provided, falls back to opening chat.
 */
export function TextSelectionTooltip() {
	const [isOpen, setIsOpen] = useState(false)
	const [position, setPosition] = useState({ x: 0, y: 0 })
	const tooltipRef = useRef(null)
	const selectionTimeoutRef = useRef(null)
	const handlerRef = useRef(null)
	const selectedTextRef = useRef("")
	// Suppress auto-close from native selectionchange for a short window after manual open
	const suppressUntilRef = useRef(0)
	const { openChat } = useChatSidebar()

	useEffect(() => {
		const updateTooltip = () => {
			const now = Date.now()
			if (now < suppressUntilRef.current) {
				return
			}
			const selection = window.getSelection()
			const text = selection?.toString().trim()
			if (!selection || !text) {
				handlerRef.current = null
				selectedTextRef.current = ""
				setIsOpen(false)
				return
			}

			const anchorNode = selection.anchorNode
			const element = anchorNode?.nodeType === Node.TEXT_NODE ? anchorNode.parentElement : anchorNode
			// Suppress tooltip in explicitly excluded areas (e.g., quizzes)
			const excludedZone = element?.closest?.("[data-askai-exclude]")
			if (excludedZone) {
				handlerRef.current = null
				selectedTextRef.current = ""
				setIsOpen(false)
				return
			}
			// Only enable tooltip within allowed selection zones
			const selectionZone = element?.closest?.("[data-selection-zone]")
			if (!selectionZone) {
				handlerRef.current = null
				selectedTextRef.current = ""
				setIsOpen(false)
				return
			}
			const askAiHandler = selectionZone?.__selectionHandlers?.onAskAI || openChat

			if (!askAiHandler) {
				handlerRef.current = null
				setIsOpen(false)
			} else {
				try {
					const range = selection.getRangeAt(0)
					const rect = range.getBoundingClientRect()

					const tooltipWidth = 152
					const tooltipHeight = 44
					const padding = 10

					const rawX = rect.left + rect.width / 2 - tooltipWidth / 2
					const x = Math.max(padding, Math.min(rawX, window.innerWidth - tooltipWidth - padding))
					let y = rect.top - tooltipHeight - padding
					if (y < padding) {
						y = rect.bottom + padding
					}

					selectedTextRef.current = text
					handlerRef.current = askAiHandler
					setPosition({ x, y })
					setIsOpen(true)
				} catch (_error) {
					handlerRef.current = null
					selectedTextRef.current = ""
					setIsOpen(false)
				}
			}
		}

		const clearSelectionTimeout = () => {
			if (selectionTimeoutRef.current) {
				clearTimeout(selectionTimeoutRef.current)
				selectionTimeoutRef.current = null
			}
		}

		const handleSelectionChange = () => {
			clearSelectionTimeout()
			selectionTimeoutRef.current = window.setTimeout(updateTooltip, 40)
		}

		const handleMouseUp = () => {
			window.setTimeout(updateTooltip, 10)
		}

		const handleClickOutside = (event) => {
			if (tooltipRef.current && !tooltipRef.current.contains(event.target)) {
				handlerRef.current = null
				selectedTextRef.current = ""
				setIsOpen(false)
			}
		}

		// Handle selections from same-document content
		document.addEventListener("mouseup", handleMouseUp)
		document.addEventListener("selectionchange", handleSelectionChange)
		document.addEventListener("mousedown", handleClickOutside)

		// Bridge for iframe-based selections (e.g., EPUB reader). Event detail: { text, clientRect }
		const handleIframeSelection = (event) => {
			try {
				const detail = event?.detail || {}
				const text = String(detail.text || "").trim()
				const rect = detail.clientRect
				if (!text || !rect) return
				// Require an allowed selection zone in the parent document
				const zone = document.querySelector("[data-selection-zone]")
				if (!zone) {
					return
				}

				const tooltipWidth = 152
				const tooltipHeight = 44
				const padding = 10

				const rawX = rect.left + rect.width / 2 - tooltipWidth / 2
				const x = Math.max(padding, Math.min(rawX, window.innerWidth - tooltipWidth - padding))
				let y = rect.top - tooltipHeight - padding
				if (y < padding) y = rect.bottom + padding

				selectedTextRef.current = text
				handlerRef.current = openChat
				setPosition({ x, y })
				setIsOpen(true)
				suppressUntilRef.current = Date.now() + 600
			} catch (_error) {}
		}
		document.addEventListener("talimio-iframe-selection", handleIframeSelection)

		// Bridge for EmbedPDF selections. Event detail: { text, clientRect }
		const handlePdfSelection = (event) => {
			try {
				const detail = event?.detail || {}
				const text = String(detail.text || "").trim()
				const rect = detail.clientRect
				if (!text || !rect) return
				// Require an allowed selection zone in the parent document
				const zone = document.querySelector("[data-selection-zone]")
				if (!zone) {
					return
				}

				const tooltipWidth = 152
				const tooltipHeight = 44
				const padding = 10

				const rawX = rect.left + rect.width / 2 - tooltipWidth / 2
				const x = Math.max(padding, Math.min(rawX, window.innerWidth - tooltipWidth - padding))
				let y = rect.top - tooltipHeight - padding
				if (y < padding) y = rect.bottom + padding

				selectedTextRef.current = text
				handlerRef.current = openChat
				setPosition({ x, y })
				setIsOpen(true)
				suppressUntilRef.current = Date.now() + 600
			} catch (_error) {}
		}
		document.addEventListener("talimio-pdf-selection", handlePdfSelection)
		return () => {
			document.removeEventListener("mouseup", handleMouseUp)
			document.removeEventListener("selectionchange", handleSelectionChange)
			document.removeEventListener("mousedown", handleClickOutside)
			document.removeEventListener("talimio-iframe-selection", handleIframeSelection)
			document.removeEventListener("talimio-pdf-selection", handlePdfSelection)
			clearSelectionTimeout()
		}
	}, [openChat])

	if (!isOpen || !handlerRef.current) {
		return null
	}

	const handleAskAiClick = () => {
		try {
			handlerRef.current?.(selectedTextRef.current)
		} finally {
			handlerRef.current = null
			selectedTextRef.current = ""
			setIsOpen(false)
			window.getSelection()?.removeAllRanges()
		}
	}

	return (
		<div
			ref={tooltipRef}
			style={{ position: "fixed", left: position.x, top: position.y, zIndex: 2147483647 }}
			className="animate-in fade-in zoom-in-95 duration-150"
		>
			<button
				type="button"
				onClick={handleAskAiClick}
				className="group flex items-center gap-2 rounded-full border border-completed/15 bg-background/95 px-4 py-2 text-sm font-medium text-completed shadow-sm shadow-completed/20 backdrop-blur transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-completed/30 focus:ring-offset-2 focus:ring-offset-background dark:border-completed/30 dark:bg-zinc-900/95 dark:text-completed dark:shadow-completed/25 dark:hover:shadow-lg dark:focus:ring-completed/40 dark:focus:ring-offset-zinc-900"
				title="Ask AI"
			>
				<span className="flex h-5 w-5 items-center justify-center text-completed transition-transform duration-150 group-hover:scale-105 dark:text-completed">
					<Sparkles className="h-4 w-4" />
				</span>
				<span className="tracking-wide">Ask AI</span>
			</button>
		</div>
	)
}

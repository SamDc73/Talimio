import { Sparkles } from "lucide-react"
import { useEffect, useRef, useState } from "react"

/**
 * Minimal floating toolbar that appears near selected text.
 * Reads handlers from the closest element carrying data-selection-zone.
 */
export function TextSelectionTooltip() {
	const [isOpen, setIsOpen] = useState(false)
	const [position, setPosition] = useState({ x: 0, y: 0 })
	const tooltipRef = useRef(null)
	const selectionTimeoutRef = useRef(null)
	const handlerRef = useRef(null)
	const selectedTextRef = useRef("")

	useEffect(() => {
		const updateTooltip = () => {
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
			const selectionZone = element?.closest?.("[data-selection-zone]")
			const askAiHandler = selectionZone?.__selectionHandlers?.onAskAI

			if (!askAiHandler) {
				setIsOpen(false)
				return
			}

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

		document.addEventListener("mouseup", handleMouseUp)
		document.addEventListener("selectionchange", handleSelectionChange)
		document.addEventListener("mousedown", handleClickOutside)

		return () => {
			document.removeEventListener("mouseup", handleMouseUp)
			document.removeEventListener("selectionchange", handleSelectionChange)
			document.removeEventListener("mousedown", handleClickOutside)
			clearSelectionTimeout()
		}
	}, [])

	if (!isOpen || !handlerRef.current) {
		return null
	}

	const handleAskAiClick = () => {
		handlerRef.current?.(selectedTextRef.current)
		handlerRef.current = null
		selectedTextRef.current = ""
		setIsOpen(false)
		window.getSelection()?.removeAllRanges()
	}

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: position.x,
				top: position.y,
				zIndex: 9999,
			}}
			className="animate-in fade-in zoom-in-95 duration-150"
		>
			<button
				type="button"
				onClick={handleAskAiClick}
				className="group flex items-center gap-2 rounded-full border border-emerald-100/80 bg-white/95 px-4 py-2 text-sm font-medium text-emerald-600 shadow-sm shadow-emerald-200/40 backdrop-blur transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-200 focus:ring-offset-2 focus:ring-offset-white dark:border-emerald-900/40 dark:bg-zinc-900/95 dark:text-emerald-300 dark:shadow-emerald-900/30 dark:hover:shadow-lg dark:focus:ring-emerald-500 dark:focus:ring-offset-zinc-900"
				title="Ask AI"
			>
				<span className="flex h-5 w-5 items-center justify-center text-emerald-500 transition-transform duration-150 group-hover:scale-105 dark:text-emerald-300">
					<Sparkles className="h-4 w-4" />
				</span>
				<span className="tracking-wide">Ask AI</span>
			</button>
		</div>
	)
}

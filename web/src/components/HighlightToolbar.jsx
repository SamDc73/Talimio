/**
 * Toolbar component for managing highlights.
 * Shows selected highlight info and provides actions.
 */

import { Copy, MessageSquare, Trash2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/button"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"

export function HighlightToolbar({ highlights = [], onDelete, className }) {
	const [hoveredHighlightId, setHoveredHighlightId] = useState(null)
	const [position, setPosition] = useState({ x: 0, y: 0 })
	const [isVisible, setIsVisible] = useState(false)
	const toolbarRef = useRef(null)
	const hideTimeoutRef = useRef(null)
	const { toast } = useToast()

	// Find the hovered highlight data
	const hoveredHighlight = highlights.find((h) => h.id === hoveredHighlightId)

	// Get the text to display (for debugging and display)
	const highlightText = hoveredHighlight?.highlight_data?.text || hoveredHighlight?.text || "Highlight text not found"

	// Global hover detection for any highlight wrapper in the document
	useEffect(() => {
		const handleOver = (e) => {
			// Clear any pending hide timeout
			if (hideTimeoutRef.current) {
				clearTimeout(hideTimeoutRef.current)
				hideTimeoutRef.current = null
			}

			// Ignore if hovering the toolbar itself
			if (toolbarRef.current?.contains(e.target)) return

			const highlightElement = e.target.closest(".text-highlight, [data-highlight-id]")
			if (!highlightElement) return

			const highlightId =
				highlightElement.getAttribute("data-highlight-id") || highlightElement.getAttribute("data-highlight-temp-id")

			if (!highlightId) return

			setHoveredHighlightId(highlightId)

			const rect = highlightElement.getBoundingClientRect()

			// With position: fixed, use viewport coordinates directly (no scroll offsets)
			setPosition({
				x: rect.left + rect.width / 2,
				y: rect.top - 60,
			})
			setIsVisible(true)
		}

		const handleOut = (e) => {
			const relatedTarget = e.relatedTarget
			if (toolbarRef.current?.contains(relatedTarget)) return
			if (relatedTarget?.closest?.(".text-highlight, [data-highlight-id]")) return

			hideTimeoutRef.current = setTimeout(() => {
				setIsVisible(false)
				setHoveredHighlightId(null)
			}, 300)
		}

		// Use capture to ensure we catch events even if stopPropagation is used elsewhere
		document.addEventListener("mouseover", handleOver, true)
		document.addEventListener("mouseout", handleOut, true)

		return () => {
			document.removeEventListener("mouseover", handleOver, true)
			document.removeEventListener("mouseout", handleOut, true)
			if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current)
		}
	}, [])

	// Handle toolbar hover to keep it visible
	const handleToolbarEnter = () => {
		if (hideTimeoutRef.current) {
			clearTimeout(hideTimeoutRef.current)
			hideTimeoutRef.current = null
		}
	}

	const handleToolbarLeave = () => {
		hideTimeoutRef.current = setTimeout(() => {
			setIsVisible(false)
			setHoveredHighlightId(null)
		}, 200)
	}

	// Handle copy to clipboard
	const handleCopy = () => {
		if (hoveredHighlight) {
			const text = hoveredHighlight.highlight_data?.text || hoveredHighlight.text || ""
			navigator.clipboard.writeText(text)
			toast({
				title: "Copied to clipboard",
				description: `"${text.substring(0, 50)}${text.length > 50 ? "..." : ""}"`,
			})
			setIsVisible(false)
		}
	}

	// Handle delete
	const handleDelete = () => {
		if (hoveredHighlightId) {
			onDelete(hoveredHighlightId)
			setIsVisible(false)
			setHoveredHighlightId(null)
			// Defer toast/UI feedback to hook delete mutation handlers
		}
	}

	if (!isVisible) return null

	return (
		<div
			ref={toolbarRef}
			role="toolbar"
			aria-label="Highlight actions"
			className={cn(
				"highlight-toolbar fixed z-50 bg-white border rounded-lg shadow-lg p-2 flex gap-1",
				"transition-all duration-200",
				className
			)}
			style={{
				left: `${position.x}px`,
				top: `${position.y}px`,
				transform: "translateX(-50%)",
			}}
			onMouseEnter={handleToolbarEnter}
			onMouseLeave={handleToolbarLeave}
		>
			{/* Show preview text if available */}
			{highlightText && highlightText !== "Highlight text not found" && (
				<div className="text-xs text-gray-100-foreground px-2 py-1 max-w-48 truncate border-r">
					"{highlightText.substring(0, 40)}
					{highlightText.length > 40 ? "..." : ""}"
				</div>
			)}

			<Button size="sm" variant="ghost" onClick={handleCopy} title="Copy text">
				<Copy className="h-4 w-4" />
			</Button>

			<Button
				size="sm"
				variant="ghost"
				onClick={() => {
					// Future: Add note functionality
				}}
				title="Add note"
			>
				<MessageSquare className="h-4 w-4" />
			</Button>

			<Button
				size="sm"
				variant="ghost"
				onClick={handleDelete}
				title="Delete highlight"
				className="text-red-500 hover:text-red-500"
			>
				<Trash2 className="h-4 w-4" />
			</Button>
		</div>
	)
}

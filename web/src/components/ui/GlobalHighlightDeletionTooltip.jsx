import { Trash2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"

/**
 * Global highlight deletion tooltip that appears when a highlight is clicked.
 * Features the same glassmorphism design as GlobalTextSelectionTooltip.
 *
 * This is a singleton component - only one should exist in the app.
 */
export function GlobalHighlightDeletionTooltip() {
	const [isOpen, setIsOpen] = useState(false)
	const [highlightId, setHighlightId] = useState(null)
	const [deleteHandler, setDeleteHandler] = useState(null)
	const [position, setPosition] = useState({ x: 0, y: 0 })
	const tooltipRef = useRef(null)

	useEffect(() => {
		const handleHighlightClick = (event) => {
			// Check if this is a highlight deletion request
			const { detail } = event
			if (!detail?.highlightId || !detail?.deleteHandler || !detail?.position) return

			setHighlightId(detail.highlightId)
			setDeleteHandler(() => detail.deleteHandler)

			// Calculate tooltip position
			const tooltipHeight = 50
			const tooltipWidth = 120
			const padding = 10

			const x = detail.position.x - tooltipWidth / 2
			const y = detail.position.y - tooltipHeight - padding

			setPosition({ x, y })
			setIsOpen(true)
		}

		const handleClickOutside = (e) => {
			if (tooltipRef.current && !tooltipRef.current.contains(e.target)) {
				setIsOpen(false)
			}
		}

		const handleHideTooltip = () => {
			setIsOpen(false)
		}

		// Listen for custom events from highlights
		window.addEventListener("highlight-delete-tooltip", handleHighlightClick)
		window.addEventListener("hide-highlight-tooltip", handleHideTooltip)
		document.addEventListener("mousedown", handleClickOutside)

		return () => {
			window.removeEventListener("highlight-delete-tooltip", handleHighlightClick)
			window.removeEventListener("hide-highlight-tooltip", handleHideTooltip)
			document.removeEventListener("mousedown", handleClickOutside)
		}
	}, [])

	const handleDeleteClick = () => {
		if (deleteHandler && highlightId) {
			deleteHandler(highlightId)
		}
		setIsOpen(false)
	}

	if (!isOpen || !deleteHandler) return null

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: position.x,
				top: position.y,
				zIndex: 9999,
			}}
			className="relative"
		>
			{/* Subtle gradient background - red/orange theme for deletion */}
			<div className="absolute inset-0 bg-gradient-to-r from-red-600/20 via-orange-600/20 to-pink-600/20 rounded-full blur-2xl" />

			{/* Main container with glassmorphism effect */}
			<div className="relative flex items-center gap-0.5 p-1 bg-white/10 dark:bg-gray-900/40 backdrop-blur-xl rounded-full shadow-2xl border border-white/20 dark:border-gray-700/30">
				<button
					type="button"
					onClick={handleDeleteClick}
					className="group flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-900 dark:text-white hover:bg-white/20 dark:hover:bg-white/10 rounded-full transition-all duration-200 hover:scale-105"
					title="Delete highlight"
				>
					<Trash2 className="w-3.5 h-3.5 transition-transform group-hover:rotate-12" />
					<span className="hidden sm:inline-block animate-in fade-in duration-200">Delete</span>
				</button>
			</div>
		</div>
	)
}

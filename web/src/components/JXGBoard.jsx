import JXG from "jsxgraph"
import { RotateCcw, ZoomIn, ZoomOut } from "lucide-react"
import { useEffect, useId, useMemo, useRef, useState } from "react"
import { Button } from "@/components/Button"
import { cn } from "@/lib/utils"

const DEFAULT_BOUNDING_BOX = [-8, 8, 8, -8]
const DEFAULT_BOARD_HEIGHT = "clamp(260px, 46vw, 420px)"
const OBSERVER_ROOT_MARGIN = "180px 0px"
const LINE_SCROLL_DELTA_PX = 16
const MIN_SMOOTH_ZOOM_FACTOR = 1.02
const MAX_SMOOTH_ZOOM_FACTOR = 1.18

const BOARD_THEME_CLASSES = {
	talimio: "border-border/70 bg-muted/20",
	classic: "border-border bg-background",
	minimal: "border-border/50 bg-background/70",
}

function resolveTheme(theme) {
	if (theme === "classic" || theme === "minimal") {
		return theme
	}
	return "talimio"
}

function resolveBoundingBox(boundingBox) {
	if (!Array.isArray(boundingBox) || boundingBox.length !== 4) {
		return DEFAULT_BOUNDING_BOX
	}

	const parsed = boundingBox.map(Number)
	if (parsed.some((value) => Number.isNaN(value))) {
		return DEFAULT_BOUNDING_BOX
	}

	return parsed
}

function readCssColor(cssVariable, fallback) {
	if (typeof window === "undefined") {
		return fallback
	}

	const value = getComputedStyle(document.documentElement).getPropertyValue(cssVariable).trim()
	return value || fallback
}

function getThemeOptions(theme) {
	if (theme === "classic") {
		return {
			defaultAxes: {
				x: { strokeColor: "#1f2937", highlightStrokeColor: "#1f2937" },
				y: { strokeColor: "#1f2937", highlightStrokeColor: "#1f2937" },
			},
			grid: { strokeColor: "#d1d5db", strokeOpacity: 0.55, dash: 1 },
			point: { fillColor: "#1f4ed8", strokeColor: "#1f4ed8", size: 3 },
			line: { strokeColor: "#1f4ed8" },
			curve: { strokeColor: "#1f4ed8" },
			text: { strokeColor: "#111827" },
		}
	}

	if (theme === "minimal") {
		return {
			defaultAxes: {
				x: { strokeColor: "#9ca3af", highlightStrokeColor: "#6b7280" },
				y: { strokeColor: "#9ca3af", highlightStrokeColor: "#6b7280" },
			},
			grid: { strokeColor: "#e5e7eb", strokeOpacity: 0.4, dash: 1 },
			point: { fillColor: "#4b5563", strokeColor: "#4b5563", size: 3 },
			line: { strokeColor: "#4b5563" },
			curve: { strokeColor: "#4b5563" },
			text: { strokeColor: "#4b5563" },
		}
	}

	const primaryColor = readCssColor("--color-primary", "#16a34a")
	const borderColor = readCssColor("--color-border", "#d4d4d8")
	const mutedColor = readCssColor("--color-muted-foreground", "#64748b")

	return {
		defaultAxes: {
			x: { strokeColor: borderColor, highlightStrokeColor: primaryColor },
			y: { strokeColor: borderColor, highlightStrokeColor: primaryColor },
		},
		grid: { strokeColor: borderColor, strokeOpacity: 0.45, dash: 1 },
		point: { fillColor: primaryColor, strokeColor: primaryColor, size: 3 },
		line: { strokeColor: primaryColor, highlightStrokeColor: primaryColor },
		curve: { strokeColor: primaryColor, highlightStrokeColor: primaryColor },
		text: { strokeColor: mutedColor },
	}
}

export function JXGBoard({
	boundingBox = DEFAULT_BOUNDING_BOX,
	axis = true,
	grid = false,
	keepAspectRatio = false,
	theme = "talimio",
	className,
	style,
	onEvent,
	setup,
}) {
	const rawId = useId()
	const boardId = useMemo(() => `jxg-board-${rawId.replaceAll(":", "")}`, [rawId])
	const boardHostRef = useRef(null)
	const boardRef = useRef(null)
	const setupRef = useRef(setup)
	const onEventRef = useRef(onEvent)
	const [isVisible, setIsVisible] = useState(false)

	const resolvedTheme = resolveTheme(theme)
	const boundingBoxKey = useMemo(() => resolveBoundingBox(boundingBox).join(","), [boundingBox])
	const handleZoomIn = () => {
		boardRef.current?.zoomIn?.()
	}
	const handleZoomOut = () => {
		boardRef.current?.zoomOut?.()
	}
	const handleResetView = () => {
		boardRef.current?.zoom100?.()
	}

	useEffect(() => {
		setupRef.current = setup
	}, [setup])

	useEffect(() => {
		onEventRef.current = onEvent
	}, [onEvent])

	useEffect(() => {
		if (isVisible || !boardHostRef.current) {
			return
		}

		if (typeof IntersectionObserver !== "function") {
			setIsVisible(true)
			return
		}

		const observer = new IntersectionObserver(
			(entries) => {
				const [entry] = entries
				if (entry?.isIntersecting) {
					setIsVisible(true)
					observer.disconnect()
				}
			},
			{ rootMargin: OBSERVER_ROOT_MARGIN }
		)

		observer.observe(boardHostRef.current)
		return () => {
			observer.disconnect()
		}
	}, [isVisible])

	useEffect(() => {
		if (!isVisible || !boardHostRef.current || boardRef.current) {
			return
		}

		const resolvedBoundingBox = boundingBoxKey.split(",").map(Number)
		const hostElement = boardHostRef.current
		const themeOptions = getThemeOptions(resolvedTheme)

		const board = JXG.JSXGraph.initBoard(boardId, {
			boundingbox: resolvedBoundingBox,
			axis,
			grid,
			keepaspectratio: keepAspectRatio,
			showNavigation: false,
			showCopyright: false,
			pan: { enabled: true, needTwoFingers: true },
			zoom: { enabled: true, wheel: false, pinch: true, factorX: 1.12, factorY: 1.12 },
			...themeOptions,
		})
		boardRef.current = board

		const smoothWheelZoom = (event) => {
			if (!event.ctrlKey) {
				return
			}

			event.preventDefault()

			let deltaY = event.deltaY
			if (event.deltaMode === 1) {
				deltaY *= LINE_SCROLL_DELTA_PX
			} else if (event.deltaMode === 2) {
				deltaY *= window.innerHeight
			}

			const magnitude = Math.min(Math.abs(deltaY), 120)
			const smoothZoomFactor = Math.min(
				MAX_SMOOTH_ZOOM_FACTOR,
				Math.max(MIN_SMOOTH_ZOOM_FACTOR, Math.exp(magnitude * 0.0014))
			)

			const coords = new JXG.Coords(JXG.COORDS_BY_SCREEN, board.getMousePosition(event), board)
			const zoomCenterX = coords.usrCoords[1]
			const zoomCenterY = coords.usrCoords[2]
			const previousFactorX = board.attr.zoom.factorx
			const previousFactorY = board.attr.zoom.factory

			board.attr.zoom.factorx = smoothZoomFactor
			board.attr.zoom.factory = smoothZoomFactor
			if (deltaY < 0) {
				board.zoomIn(zoomCenterX, zoomCenterY)
			} else {
				board.zoomOut(zoomCenterX, zoomCenterY)
			}
			board.attr.zoom.factorx = previousFactorX
			board.attr.zoom.factory = previousFactorY
		}

		hostElement.addEventListener("wheel", smoothWheelZoom, { passive: false })

		const animationStops = []
		const emit = (name, payload) => {
			if (typeof onEventRef.current === "function") {
				onEventRef.current({ name, payload })
			}
		}

		const startAnimation = (frameFn) => {
			if (typeof frameFn !== "function") {
				return () => {}
			}

			let animationFrameId = 0
			let isRunning = true
			let frame = 0
			let startMs = 0
			let previousMs = 0

			const tick = (nowMs) => {
				if (!isRunning) {
					return
				}

				if (startMs === 0) {
					startMs = nowMs
					previousMs = nowMs
				}

				frame += 1
				const dtMs = nowMs - previousMs
				previousMs = nowMs
				frameFn({
					elapsedMs: nowMs - startMs,
					dtMs,
					nowMs,
					frame,
				})
				animationFrameId = window.requestAnimationFrame(tick)
			}

			animationFrameId = window.requestAnimationFrame(tick)

			const stop = () => {
				if (!isRunning) {
					return
				}
				isRunning = false
				window.cancelAnimationFrame(animationFrameId)
			}

			animationStops.push(stop)
			return stop
		}

		// Clean theme object to expose to setup
		const exposedTheme = {
			name: resolvedTheme,
			colors: {
				primary: themeOptions.point?.fillColor || "#16a34a",
				text: themeOptions.text?.strokeColor || "#64748b",
				grid: themeOptions.grid?.strokeColor || "#d4d4d8",
				axis: themeOptions.defaultAxes?.x?.strokeColor || "#d4d4d8",
			},
		}

		const setupCleanup =
			typeof setupRef.current === "function"
				? setupRef.current({
						board,
						JXG,
						container: boardHostRef.current,
						emit,
						startAnimation,
						theme: exposedTheme,
					})
				: null

		return () => {
			for (const stop of animationStops) {
				stop()
			}
			if (typeof setupCleanup === "function") {
				setupCleanup()
			}
			hostElement.removeEventListener("wheel", smoothWheelZoom)
			board.removeEventHandlers?.()
			JXG.JSXGraph.freeBoard(board)
			boardRef.current = null
		}
	}, [axis, boardId, boundingBoxKey, grid, isVisible, keepAspectRatio, resolvedTheme])

	return (
		<section
			className={cn(
				"group relative my-6 overflow-hidden rounded-xl border shadow-sm",
				BOARD_THEME_CLASSES[resolvedTheme],
				className
			)}
			style={style}
		>
			<div
				id={boardId}
				ref={boardHostRef}
				className="w-full bg-background/80 transition-colors duration-500"
				style={{ height: DEFAULT_BOARD_HEIGHT, minHeight: "260px", touchAction: "none" }}
			/>

			<div className="absolute right-3 top-3 flex flex-col items-center gap-0.5 rounded-full border border-border/40 bg-background/60 p-1 opacity-0 shadow-sm backdrop-blur-md transition-all duration-300 focus-within:opacity-100 hover:bg-background/80 group-hover:opacity-100">
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="h-8 w-8 rounded-full text-muted-foreground transition-colors hover:bg-background/80 hover:text-foreground"
					onClick={handleZoomIn}
					aria-label="Zoom in"
				>
					<ZoomIn className="size-4 " />
				</Button>
				<div className="my-0.5 h-px w-3 bg-border/50" />
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="h-8 w-8 rounded-full text-muted-foreground transition-colors hover:bg-background/80 hover:text-foreground"
					onClick={handleZoomOut}
					aria-label="Zoom out"
				>
					<ZoomOut className="size-4 " />
				</Button>
				<div className="my-0.5 h-px w-3 bg-border/50" />
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="h-8 w-8 rounded-full text-muted-foreground transition-colors hover:bg-background/80 hover:text-foreground"
					onClick={handleResetView}
					aria-label="Reset view"
				>
					<RotateCcw className="size-3.5 " />
				</Button>
			</div>
		</section>
	)
}

export default JXGBoard

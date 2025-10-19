import { createPluginRegistration } from "@embedpdf/core"
import { EmbedPDF } from "@embedpdf/core/react"
import { usePdfiumEngine } from "@embedpdf/engines/react"
import { ignore } from "@embedpdf/models"
import {
	GlobalPointerProvider,
	InteractionManagerPluginPackage,
	PagePointerProvider,
} from "@embedpdf/plugin-interaction-manager/react"
import { LoaderPluginPackage } from "@embedpdf/plugin-loader/react"
import { RenderLayer, RenderPluginPackage } from "@embedpdf/plugin-render/react"
import { Scroller, ScrollPluginPackage, useScroll } from "@embedpdf/plugin-scroll/react"
import { SelectionLayer, SelectionPluginPackage, useSelectionCapability } from "@embedpdf/plugin-selection/react"
import { Viewport, ViewportPluginPackage } from "@embedpdf/plugin-viewport/react"
import { ZoomMode } from "@embedpdf/plugin-zoom"
import { useZoom, ZoomPluginPackage } from "@embedpdf/plugin-zoom/react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useBookActions, useBookReadingState, useBookStoreHydrated } from "../hooks/useBookState"

function ViewerRuntime({
	bookId,
	registerApi,
	getBookReadingState,
	updateBookReadingState,
	hasRestoredPage: HasRestoredPage,
	onMarkPageRestored: OnMarkPageRestored,
}) {
	const pageCtxRef = useRef(new Map()) // pageIndex -> { el: HTMLElement, scale: number }
	const { provides: selection } = useSelectionCapability()
	const zoomRestoredRef = useRef(false)

	// Runtime selection bridge + zoom/page persistence
	const { provides: scrollProvides, state: scrollState } = useScroll()
	const { provides: zoomProvides, state: zoomState } = useZoom()
	const currentZoomLevel = zoomState?.currentZoomLevel

	// Expose a narrow API for header controls
	useEffect(() => {
		if (!registerApi) return
		const api = {
			zoomIn: () => zoomProvides?.zoomIn?.(),
			zoomOut: () => zoomProvides?.zoomOut?.(),
			fitToScreen: () => zoomProvides?.requestZoom?.(ZoomMode.FitPage),
			goToPage: (pageNumber) => scrollProvides?.scrollToPage?.({ pageNumber }),
		}
		registerApi(api)
		// Intentionally no cleanup to avoid clearing API when parent callback identity changes
	}, [registerApi, zoomProvides, scrollProvides])

	// Persist zoom changes using EmbedPDF Zoom state (fractional value, e.g. 1.0 = 100%)
	useEffect(() => {
		if (typeof currentZoomLevel !== "number" || !Number.isFinite(currentZoomLevel)) return
		// Avoid persisting initial plugin auto/default zoom before restoration completes
		if (!HasRestoredPage) return
		const pct = Math.round(currentZoomLevel * 100)
		const rs = getBookReadingState?.(bookId)
		const requestedLevel = zoomState?.zoomLevel
		const zoomMode = typeof requestedLevel === "string" ? requestedLevel : null
		if (rs?.zoomLevel === pct && (rs?.zoomMode ?? null) === zoomMode) return
		updateBookReadingState?.(bookId, { zoomLevel: pct, zoomMode })
	}, [bookId, currentZoomLevel, zoomState?.zoomLevel, HasRestoredPage, getBookReadingState, updateBookReadingState])

	// Persist current page and total pages when scroll state updates
	useEffect(() => {
		const page = scrollState?.currentPage
		const total = scrollState?.totalPages
		// Require valid values
		if (!bookId || !total || !page) return
		// Avoid clobbering saved state before restoration
		if (!HasRestoredPage) return
		const rs = getBookReadingState?.(bookId)
		if (rs?.currentPage === page && rs?.totalPages === total) return
		updateBookReadingState?.(bookId, { currentPage: page, totalPages: total })
	}, [
		bookId,
		scrollState?.currentPage,
		scrollState?.totalPages,
		HasRestoredPage,
		getBookReadingState,
		updateBookReadingState,
	])

	// Restore persisted page once when document metrics are ready
	useEffect(() => {
		if (!scrollProvides) return
		const total = scrollState?.totalPages
		if (!total || total <= 0) return
		if (HasRestoredPage) return
		const savedPage = getBookReadingState?.(bookId)?.currentPage
		if (typeof savedPage === "number" && savedPage > 0) {
			scrollProvides.scrollToPage?.({ pageNumber: savedPage, behavior: "instant" })
		}
		// Whether or not we scrolled, mark restored so persistence can start
		OnMarkPageRestored?.()
	}, [scrollProvides, scrollState?.totalPages, HasRestoredPage, OnMarkPageRestored, bookId, getBookReadingState])

	// Restore persisted zoom once zoom state is known
	useEffect(() => {
		if (!zoomProvides) return
		const current = zoomState?.currentZoomLevel
		if (typeof current !== "number" || !Number.isFinite(current)) return
		// Avoid clobbering saved zoom before restoration
		if (!HasRestoredPage) return
		if (zoomRestoredRef.current) return
		const saved = getBookReadingState?.(bookId)
		const savedMode = saved?.zoomMode
		const savedZoomPct = saved?.zoomLevel
		if (typeof savedMode === "string" && savedMode) {
			zoomProvides.requestZoom?.(savedMode)
		} else if (typeof savedZoomPct === "number" && savedZoomPct > 0) {
			const savedLevel = savedZoomPct / 100
			if (Math.abs(savedLevel - current) > 0.001) {
				zoomProvides.requestZoom?.(savedLevel)
			}
		}
		// Mark zoom restored so subsequent user zooms do not trigger a restore loop
		zoomRestoredRef.current = true
	}, [zoomProvides, zoomState?.currentZoomLevel, HasRestoredPage, bookId, getBookReadingState])

	const renderPage = useCallback(
		({ width, height, pageIndex, scale, rotation }) => (
			<div
				className="mx-auto"
				style={{
					width,
					height,
					position: "relative",
				}}
				ref={(el) => {
					if (el) {
						pageCtxRef.current.set(pageIndex, { el, scale })
					} else {
						pageCtxRef.current.delete(pageIndex)
					}
				}}
			>
				<PagePointerProvider
					pageIndex={pageIndex}
					pageWidth={width}
					pageHeight={height}
					rotation={rotation}
					scale={scale}
				>
					<RenderLayer pageIndex={pageIndex} scale={scale} />
					<SelectionLayer pageIndex={pageIndex} scale={scale} background="Highlight" />
				</PagePointerProvider>
			</div>
		),
		[]
	)

	// When a PDF selection ends, dispatch a simple event with selected text and a window clientRect
	useEffect(() => {
		if (!selection) return

		return selection.onEndSelection(() => {
			// Get the selected text (array of lines)
			const textTask = selection.getSelectedText()
			textTask.wait((lines) => {
				const text = Array.isArray(lines) ? lines.join("\n") : String(lines || "")

				// Get bounding rects for pages and pick the first non-empty
				const rects = selection.getBoundingRects?.() || []
				const first = rects.find(Boolean)
				if (!first) return
				const ctx = pageCtxRef.current.get(first.page)
				if (!ctx || !ctx.el || !ctx.scale) return

				const pageBox = ctx.el.getBoundingClientRect()
				const r = first.rect
				const scale = ctx.scale
				const clientRect = {
					left: pageBox.left + r.origin.x * scale,
					top: pageBox.top + r.origin.y * scale,
					right: pageBox.left + (r.origin.x + r.size.width) * scale,
					bottom: pageBox.top + (r.origin.y + r.size.height) * scale,
					width: r.size.width * scale,
					height: r.size.height * scale,
				}

				document.dispatchEvent(new CustomEvent("talimio-pdf-selection", { detail: { text, clientRect } }))
			}, ignore)
		})
	}, [selection])

	return (
		<Viewport className="h-full w-full">
			<Scroller renderPage={renderPage} />
		</Viewport>
	)
}

function PDFViewer({ url, onTextSelection: _onTextSelection, bookId, registerApi = null }) {
	// Component-local state (ephemeral UI)
	const [hasRestoredPage, setHasRestoredPage] = useState(false)
	const [pdfBlobUrl, setPdfBlobUrl] = useState(null)
	const [loadError, setLoadError] = useState(null)
	const previousSourceRef = useRef({ url: null, bookId: null })
	const blobUrlRef = useRef(null)
	const initialZoomLevelRef = useRef(null)
	const initialZoomModeRef = useRef(null)
	const initialPageRef = useRef(null)

	// Engine and store
	const { engine, isLoading: engineLoading } = usePdfiumEngine()
	const readingState = useBookReadingState(bookId)
	const { updateBookReadingState } = useBookActions()
	const storeHydrated = useBookStoreHydrated()

	// Capture initial snapshots at render time (before plugin creation) to avoid flicker
	if (
		storeHydrated &&
		initialZoomLevelRef.current === null &&
		typeof readingState?.zoomLevel === "number" &&
		readingState.zoomLevel > 0
	) {
		initialZoomLevelRef.current = readingState.zoomLevel
	}
	if (
		storeHydrated &&
		initialZoomModeRef.current === null &&
		typeof readingState?.zoomMode === "string" &&
		readingState.zoomMode
	) {
		initialZoomModeRef.current = readingState.zoomMode
	}
	if (
		storeHydrated &&
		initialPageRef.current === null &&
		storeHydrated &&
		typeof readingState?.currentPage === "number" &&
		readingState.currentPage > 0
	) {
		initialPageRef.current = readingState.currentPage
	}

	// Mark restored page flag once runtime confirms
	const markPageRestored = useCallback(() => {
		setHasRestoredPage(true)
	}, [])

	// Reset page restoration when source changes
	useEffect(() => {
		const hasSourceChanged = previousSourceRef.current.url !== url || previousSourceRef.current.bookId !== bookId
		if (hasSourceChanged) {
			setHasRestoredPage(false)
			previousSourceRef.current = { url, bookId }
		}
	}, [url, bookId])

	// Optionally restore persisted zoom/page once store is hydrated
	useEffect(() => {
		if (!storeHydrated) return
		if (initialZoomLevelRef.current === null) {
			const z = readingState?.zoomLevel
			if (typeof z === "number" && z > 0) initialZoomLevelRef.current = z
		}
		if (initialZoomModeRef.current === null) {
			const m = readingState?.zoomMode
			if (typeof m === "string" && m) initialZoomModeRef.current = m
		}
		if (initialPageRef.current === null) {
			const p = readingState?.currentPage
			if (typeof p === "number" && p > 0) initialPageRef.current = p
		}
	}, [storeHydrated, readingState?.zoomLevel, readingState?.zoomMode, readingState?.currentPage])
	// Fetch PDF and create blob URL (EmbedPDF needs blob URL for auth endpoints)
	useEffect(() => {
		if (!url) {
			if (blobUrlRef.current) {
				URL.revokeObjectURL(blobUrlRef.current)
				blobUrlRef.current = null
			}
			setPdfBlobUrl(null)
			setLoadError(null)
			return
		}

		let cancelled = false

		const fetchPdf = async () => {
			try {
				setLoadError(null)
				const response = await fetch(url, { credentials: "include" })
				if (!response.ok) {
					throw new Error(`Failed to load PDF: ${response.status}`)
				}
				const blob = await response.blob()
				if (cancelled) return
				if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current)
				const blobUrl = URL.createObjectURL(blob)
				blobUrlRef.current = blobUrl
				setPdfBlobUrl(blobUrl)
			} catch (error) {
				if (!cancelled) {
					setLoadError(error.message)
					setPdfBlobUrl(null)
				}
			}
		}

		fetchPdf()
		return () => {
			cancelled = true
		}
	}, [url])

	// Cleanup blob URL on unmount
	useEffect(() => {
		return () => {
			if (blobUrlRef.current) {
				URL.revokeObjectURL(blobUrlRef.current)
			}
		}
	}, [])

	const plugins = useMemo(() => {
		if (!pdfBlobUrl) {
			return []
		}

		const documentId = bookId ? `book-${bookId}` : "pdf-document"
		// Prefer saved zoomMode (Automatic/FitPage/FitWidth). If absent, use saved numeric zoom; else Automatic.
		const defaultZoom =
			typeof initialZoomModeRef.current === "string" && initialZoomModeRef.current
				? initialZoomModeRef.current
				: typeof initialZoomLevelRef.current === "number" && initialZoomLevelRef.current > 0
					? initialZoomLevelRef.current / 100
					: ZoomMode.Automatic
		return [
			createPluginRegistration(LoaderPluginPackage, {
				loadingOptions: {
					type: "url",
					pdfFile: {
						id: documentId,
						url: pdfBlobUrl,
					},
				},
			}),
			createPluginRegistration(ViewportPluginPackage),
			createPluginRegistration(ScrollPluginPackage, {
				initialPage:
					typeof initialPageRef.current === "number" && initialPageRef.current > 0 ? initialPageRef.current : undefined,
			}),
			createPluginRegistration(RenderPluginPackage),
			createPluginRegistration(ZoomPluginPackage, {
				defaultZoomLevel: defaultZoom,
			}),
			createPluginRegistration(InteractionManagerPluginPackage),
			createPluginRegistration(SelectionPluginPackage),
		]
	}, [bookId, pdfBlobUrl])

	if (!url) {
		return (
			<div className="flex h-64 items-center justify-center rounded-lg bg-muted/40">
				<p className="text-muted-foreground">No PDF URL provided</p>
			</div>
		)
	}

	if (loadError) {
		return (
			<div className="flex h-64 items-center justify-center rounded-lg bg-muted/40">
				<div className="text-center">
					<p className="text-destructive font-semibold">Failed to load PDF</p>
					<p className="mt-2 text-xs text-destructive/80">{loadError}</p>
				</div>
			</div>
		)
	}

	if (!storeHydrated) {
		return (
			<div className="flex h-64 items-center justify-center rounded-lg bg-muted/40">
				<p className="text-muted-foreground">Preparing reader…</p>
			</div>
		)
	}

	if (!pdfBlobUrl || engineLoading || !engine || plugins.length === 0) {
		return (
			<div className="flex h-64 items-center justify-center rounded-lg bg-muted/40">
				<p className="text-muted-foreground">Loading PDF…</p>
			</div>
		)
	}

	return (
		<div className="relative flex h-full flex-col overflow-auto bg-muted py-8 dark:bg-background/80">
			<EmbedPDF engine={engine} plugins={plugins}>
				<GlobalPointerProvider>
					<div className="flex h-full w-full justify-center" data-selection-zone="true">
						<ViewerRuntime
							bookId={bookId}
							registerApi={registerApi}
							getBookReadingState={(id) => (id === bookId ? readingState : null)}
							updateBookReadingState={updateBookReadingState}
							hasRestoredPage={hasRestoredPage}
							onMarkPageRestored={markPageRestored}
						/>
					</div>
				</GlobalPointerProvider>
			</EmbedPDF>
		</div>
	)
}

export default PDFViewer

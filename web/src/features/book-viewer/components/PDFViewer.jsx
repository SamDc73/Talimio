import { createPluginRegistration } from "@embedpdf/core"
import { EmbedPDF } from "@embedpdf/core/react"
import { usePdfiumEngine } from "@embedpdf/engines/react"
import {
	GlobalPointerProvider,
	InteractionManagerPluginPackage,
	PagePointerProvider,
} from "@embedpdf/plugin-interaction-manager/react"
import { LoaderPluginPackage } from "@embedpdf/plugin-loader/react"
import { RenderLayer, RenderPluginPackage } from "@embedpdf/plugin-render/react"
import { Scroller, ScrollPluginPackage, useScroll } from "@embedpdf/plugin-scroll/react"
import { SelectionLayer, SelectionPluginPackage } from "@embedpdf/plugin-selection/react"
import { Viewport, ViewportPluginPackage } from "@embedpdf/plugin-viewport/react"
import { useZoom, ZoomMode, ZoomPluginPackage } from "@embedpdf/plugin-zoom/react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useBookActions, useBookReadingState, useBookStoreHydrated } from "../../hooks/useBookState"

function ViewerRuntime({
	bookId,
	registerApi,
	getBookReadingState,
	updateBookReadingState,
	hasRestoredPage,
	onMarkPageRestored,
}) {
	const { provides: scrollProvides, state: scrollState } = useScroll()
	const { provides: zoomProvides, state: zoomState } = useZoom()
	const currentZoomLevel = zoomState?.currentZoomLevel
	const hasAppliedStoredZoomRef = useRef(false)
	const pendingRestoreTargetRef = useRef(null)

	useEffect(() => {
		if (!scrollProvides || !bookId) {
			return undefined
		}

		return scrollProvides.onPageChange(({ pageNumber, totalPages }) => {
			const currentState = getBookReadingState(bookId)

			if (!hasRestoredPage) {
				if (pendingRestoreTargetRef.current && pageNumber === pendingRestoreTargetRef.current) {
					pendingRestoreTargetRef.current = null
					onMarkPageRestored()
				}
				if (pendingRestoreTargetRef.current && pageNumber !== pendingRestoreTargetRef.current) {
					return
				}
				if (!pendingRestoreTargetRef.current && currentState?.currentPage && currentState.currentPage !== pageNumber) {
					return
				}
			}

			if (currentState?.currentPage !== pageNumber) {
				updateBookReadingState(bookId, { currentPage: pageNumber, totalPages })
			}
		})
	}, [bookId, getBookReadingState, hasRestoredPage, onMarkPageRestored, scrollProvides, updateBookReadingState])

	useEffect(() => {
		if (!scrollProvides || hasRestoredPage || !bookId || !scrollState?.totalPages) {
			return
		}

		const readingState = getBookReadingState(bookId)
		const targetPage = readingState?.currentPage
		if (!targetPage || targetPage <= 0) {
			return
		}

		if (targetPage > scrollState.totalPages) {
			pendingRestoreTargetRef.current = targetPage
			return
		}

		if (scrollState.currentPage === targetPage) {
			pendingRestoreTargetRef.current = null
			onMarkPageRestored()
			return
		}

		if (pendingRestoreTargetRef.current !== targetPage) {
			pendingRestoreTargetRef.current = targetPage
		}

		scrollProvides.scrollToPage({ pageNumber: targetPage, behavior: "instant" })
	}, [
		bookId,
		getBookReadingState,
		hasRestoredPage,
		onMarkPageRestored,
		scrollProvides,
		scrollState.currentPage,
		scrollState.totalPages,
	])

	useEffect(() => {
		if (!scrollProvides || hasRestoredPage) {
			return
		}
		const off = scrollProvides.onLayoutReady?.(() => {
			const target = pendingRestoreTargetRef.current
			if (!target) return
			scrollProvides.scrollToPage({ pageNumber: target, behavior: "instant" })
		})
		return () => off?.()
	}, [scrollProvides, hasRestoredPage])

	useEffect(() => {
		if (!registerApi || !scrollProvides || !zoomProvides) {
			return
		}
		registerApi({
			goToPage: (pageNumber) => {
				scrollProvides.scrollToPage({ pageNumber })
			},
			fitToScreen: () => zoomProvides.requestZoom(ZoomMode.FitWidth),
			getCurrentPage: () => scrollProvides.getCurrentPage?.() ?? 1,
			getTotalPages: () => scrollProvides.getTotalPages?.() ?? 0,
			zoomIn: zoomProvides.zoomIn,
			zoomOut: zoomProvides.zoomOut,
		})
	}, [registerApi, scrollProvides, zoomProvides])

	useEffect(() => {
		if (!bookId || currentZoomLevel === undefined) {
			return
		}
		const storedZoom = getBookReadingState(bookId)?.zoomLevel
		const currentPct = Math.round(currentZoomLevel * 100)

		// During initialization, never overwrite a stored zoom with a different initial value.
		if (!hasAppliedStoredZoomRef.current) {
			if (typeof storedZoom === "number" && storedZoom > 0) {
				if (storedZoom !== currentPct) {
					return
				}
				// already at stored zoom; allow future persisting
				hasAppliedStoredZoomRef.current = true
			} else {
				// no stored zoom; allow persisting from now on
				hasAppliedStoredZoomRef.current = true
			}
		}

		// If not marked applied yet, do nothing
		if (!hasAppliedStoredZoomRef.current) {
			return
		}

		// Avoid redundant writes
		if (typeof storedZoom === "number" && storedZoom === currentPct) {
			return
		}

		const toPersist = currentPct
		updateBookReadingState(bookId, { zoomLevel: toPersist })
	}, [bookId, currentZoomLevel, updateBookReadingState, getBookReadingState])

	useEffect(() => {
		// Wait for zoom system to initialize (currentZoomLevel becomes defined)
		if (!bookId || !zoomProvides || hasAppliedStoredZoomRef.current || currentZoomLevel === undefined) {
			return
		}
		const storedZoom = getBookReadingState(bookId)?.zoomLevel
		if (typeof storedZoom === "number" && storedZoom > 0) {
			zoomProvides.requestZoom(storedZoom / 100)
		}
		hasAppliedStoredZoomRef.current = true
	}, [bookId, getBookReadingState, zoomProvides, currentZoomLevel])

	const renderPage = useCallback(
		({ width, height, pageIndex, scale, rotation }) => (
			<div
				className="mx-auto"
				style={{
					width,
					height,
					position: "relative",
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
	const initialPageRef = useRef(null)

	// Zustand store access via custom hooks (persistent state)
	const readingState = useBookReadingState(bookId)
	const { updateBookReadingState } = useBookActions()
	const storeHydrated = useBookStoreHydrated()

	// Capture initial snapshots at render time (before plugin creation) to reduce flicker
	if (
		initialZoomLevelRef.current === null &&
		typeof readingState?.zoomLevel === "number" &&
		readingState.zoomLevel > 0
	) {
		initialZoomLevelRef.current = readingState.zoomLevel
	}
	if (
		initialPageRef.current === null &&
		typeof readingState?.currentPage === "number" &&
		readingState.currentPage > 0
	) {
		initialPageRef.current = readingState.currentPage
	}

	const { engine, isLoading: engineLoading } = usePdfiumEngine()

	const markPageRestored = useCallback(() => {
		setHasRestoredPage(true)
	}, [])

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
				// Fetch from authenticated endpoint (cookies sent automatically)
				const response = await fetch(url, { credentials: "include" })

				if (!response.ok) {
					throw new Error(`Failed to load PDF: ${response.status}`)
				}

				const blob = await response.blob()

				if (cancelled) {
					return
				}

				// Create blob URL for EmbedPDF
				if (blobUrlRef.current) {
					URL.revokeObjectURL(blobUrlRef.current)
				}
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

	// Reset page restoration when source changes
	useEffect(() => {
		const hasSourceChanged = previousSourceRef.current.url !== url || previousSourceRef.current.bookId !== bookId
		if (hasSourceChanged) {
			setHasRestoredPage(false)
			previousSourceRef.current = { url, bookId }
		}
	}, [url, bookId])

	// Capture initial persisted zoom once (avoid plugin re-instantiation on zoom changes)
	useEffect(() => {
		if (!storeHydrated) return
		if (initialZoomLevelRef.current === null) {
			const z = readingState?.zoomLevel
			if (typeof z === "number" && z > 0) {
				initialZoomLevelRef.current = z
			}
		}
	}, [storeHydrated, readingState?.zoomLevel])

	// Capture initial persisted page once for ScrollPlugin.initialPage
	useEffect(() => {
		if (!storeHydrated) return
		if (initialPageRef.current === null) {
			const p = readingState?.currentPage
			if (typeof p === "number" && p > 0) {
				initialPageRef.current = p
			}
		}
	}, [storeHydrated, readingState?.currentPage])

	const plugins = useMemo(() => {
		if (!pdfBlobUrl) {
			return []
		}

		const documentId = bookId ? `book-${bookId}` : "pdf-document"
		// Prefer saved zoom for initial load to avoid flicker; fall back to Automatic
		const initialZoomLevel =
			typeof initialZoomLevelRef.current === "number" && initialZoomLevelRef.current > 0
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
				defaultZoomLevel: initialZoomLevel,
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
					<div className="flex h-full w-full justify-center">
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

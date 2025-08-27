/**
 * @file MinimalPDFViewer.jsx
 * @desc A minimal PDF viewer component using @embedpdf/core, based on official examples.
 */

import { createPluginRegistration } from "@embedpdf/core"
import { EmbedPDF } from "@embedpdf/core/react"
import { usePdfiumEngine } from "@embedpdf/engines/react"
import { LoaderPluginPackage } from "@embedpdf/plugin-loader"
import { RenderPluginPackage } from "@embedpdf/plugin-render"
import { RenderLayer } from "@embedpdf/plugin-render/react"
import { ScrollPluginPackage, ScrollStrategy } from "@embedpdf/plugin-scroll"
import { Scroller } from "@embedpdf/plugin-scroll/react"
import { ViewportPluginPackage } from "@embedpdf/plugin-viewport"
import { Viewport } from "@embedpdf/plugin-viewport/react"
import { ZoomPluginPackage } from "@embedpdf/plugin-zoom"
import { useZoom } from "@embedpdf/plugin-zoom/react"
import { useEffect, useRef, useState } from "react"

import { api } from "@/lib/apiClient"

function Toolbar({ onZoomIn, onZoomOut }) {
	const { provides: zoomProvides } = useZoom()

	useEffect(() => {
		if (zoomProvides) {
			onZoomIn?.(zoomProvides.zoomIn)
			onZoomOut?.(zoomProvides.zoomOut)
		}
	}, [zoomProvides, onZoomIn, onZoomOut])

	return null
}

// Main component to render the PDF viewer

export function MinimalPDFViewer({ bookId, onZoomIn, onZoomOut }) {
	const [pdfBlobUrl, setPdfBlobUrl] = useState(null)
	const [pdfBuffer, setPdfBuffer] = useState(null)
	const blobUrlRef = useRef(null)
	const [isDataLoading, setIsDataLoading] = useState(true)
	const [dataError, setDataError] = useState(null)
	const { engine, isLoading: isEngineLoading, error: engineError } = usePdfiumEngine()

	useEffect(() => {
		const loadPdf = async () => {
			setIsDataLoading(true)
			setDataError(null)
			try {
				// First, try to get a presigned URL from R2
				const presignedResponse = await api.get(`/books/${bookId}/presigned-url`)
				if (presignedResponse?.data?.url) {
					setPdfBlobUrl(presignedResponse.data.url)
				} else {
					const pdfResponse = await fetch(`/api/v1/books/${bookId}/content`, {
						credentials: "include",
						headers: {
							accept: "application/pdf",
						},
					})

					if (!pdfResponse.ok) {
						throw new Error(`Failed to load PDF: ${pdfResponse.status} ${pdfResponse.statusText}`)
					}

					// Get as ArrayBuffer for buffer loading
					const arrayBuffer = await pdfResponse.arrayBuffer()

					// Verify buffer is valid
					if (arrayBuffer.byteLength === 0) {
						throw new Error("PDF buffer is empty")
					}

					// Check PDF magic bytes for validation
					const _uint8Array = new Uint8Array(arrayBuffer)

					// Store the ArrayBuffer (not Uint8Array) as that's what the library expects
					setPdfBuffer(arrayBuffer)
				}
			} catch (err) {
				setDataError(err.message)
			} finally {
				setIsDataLoading(false)
			}
		}

		if (bookId && engine) {
			loadPdf()
		}

		return () => {
			if (blobUrlRef.current) {
				URL.revokeObjectURL(blobUrlRef.current)
				blobUrlRef.current = null
			}
		}
	}, [bookId, engine])

	if (isEngineLoading || isDataLoading) {
		return <div>Loading PDF...</div>
	}

	if (engineError) {
		return <div>Error loading PDF engine: {engineError.message}</div>
	}

	if (dataError) {
		return <div>Error: {dataError}</div>
	}

	if (!engine) {
		return <div>Engine not available.</div>
	}

	if (!pdfBlobUrl && !pdfBuffer) {
		return <div>No PDF to display.</div>
	}

	// Create loading options based on what we have
	let loadingOptions
	if (pdfBuffer) {
		loadingOptions = {
			type: "buffer",
			pdfFile: {
				id: bookId,
				content: pdfBuffer, // The library expects 'content' field with ArrayBuffer
			},
		}
	} else {
		loadingOptions = {
			type: "url",
			pdfFile: {
				id: bookId,
				url: pdfBlobUrl,
			},
			options: {
				mode: "full-fetch",
			},
		}
	}

	const plugins = [
		createPluginRegistration(LoaderPluginPackage, {
			loadingOptions,
			onLoaderEvent: (_event) => {},
			onDocumentLoaded: (_doc) => {},
			onError: (_error) => {},
		}),
		createPluginRegistration(ViewportPluginPackage, { viewportGap: 10 }),
		createPluginRegistration(ScrollPluginPackage, { strategy: ScrollStrategy.Vertical }),
		createPluginRegistration(RenderPluginPackage),
		createPluginRegistration(ZoomPluginPackage),
	]

	return (
		<EmbedPDF engine={engine} plugins={plugins}>
			{({ pluginsReady, document, error }) => {
				// Check for errors first
				if (error) {
					return (
						<div className="h-full w-full flex items-center justify-center">
							<div className="text-red-500">
								<div>Error loading PDF:</div>
								<div className="text-sm mt-2">{error.message || "Unknown error"}</div>
							</div>
						</div>
					)
				}

				return (
					<Viewport className="h-full w-full overflow-auto bg-gray-100">
						{pluginsReady && document ? (
							<>
								<Toolbar onZoomIn={onZoomIn} onZoomOut={onZoomOut} />
								<Scroller
									renderPage={({ pageIndex }) => (
										<div className="relative bg-white shadow-lg mx-auto my-4">
											<RenderLayer pageIndex={pageIndex} />
										</div>
									)}
								/>
							</>
						) : (
							<div className="h-full w-full flex items-center justify-center">
								<div>Loading PDF plugins...</div>
							</div>
						)}
					</Viewport>
				)
			}}
		</EmbedPDF>
	)
}

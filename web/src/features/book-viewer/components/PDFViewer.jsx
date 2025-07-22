import {
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useMemo,
	useRef,
	useState,
} from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { useTextSelectionTooltip } from "@/hooks/useTextSelectionTooltip";
import "./PDFViewer.css";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const PDFViewer = forwardRef(
	({ url, onPageChange, zoom = 100, onZoomChange, initialPage = 1 }, ref) => {
		const [numPages, setNumPages] = useState(null);
		const [pageNumber, setPageNumber] = useState(1);
		const [visiblePages, setVisiblePages] = useState(new Set([1, 2, 3]));
		const [pageWidth, setPageWidth] = useState(null);
		const [isZooming, setIsZooming] = useState(false);
		const [isScrolling, setIsScrolling] = useState(false);
		const containerRef = useRef(null);
		const pagesRef = useRef({});
		const zoomPointRef = useRef(null);
		const pageNumberRef = useRef(1);
		const scrollTimeoutRef = useRef(null);
		const lastValidPageRef = useRef(1);
		const scrollingTimeoutRef = useRef(null);
		const scale = zoom / 100;

		// Set up text selection handlers for PDF
		useTextSelectionTooltip(
			(text) => {
				console.log("Highlight in PDF:", text);
				// Add highlight functionality here in the future
			},
			(text) => {
				console.log("Ask AI about PDF text:", text);
				// Add AI functionality here in the future
			},
		);

		// Keep pageNumberRef in sync with pageNumber state
		useEffect(() => {
			pageNumberRef.current = pageNumber;
			lastValidPageRef.current = pageNumber;
		}, [pageNumber]);

		// Memoize document options to prevent re-renders
		const documentOptions = useMemo(
			() => ({
				cMapUrl: "cmaps/",
				cMapPacked: true,
			}),
			[],
		);

		const onDocumentLoadSuccess = (pdf) => {
			setNumPages(pdf.numPages);
			// Get the first page to determine its width
			pdf.getPage(1).then((page) => {
				const viewport = page.getViewport({ scale: 1 });
				setPageWidth(viewport.width);

				// After the page width is set, scroll to the initial page if needed
				if (initialPage > 1) {
					setTimeout(() => {
						scrollToPage(initialPage);
						setPageNumber(initialPage);
						if (onPageChange) {
							onPageChange(initialPage);
						}
					}, 100); // Small delay to ensure DOM is ready
				}
			});

			// Set initial page number
			setPageNumber(initialPage);
			lastValidPageRef.current = initialPage;
			if (onPageChange && initialPage === 1) {
				onPageChange(initialPage);
			}
		};

		// Calculate fit to width scale
		const calculateFitToWidth = useCallback(() => {
			if (!containerRef.current || !pageWidth) return;

			const containerWidth = containerRef.current.clientWidth;
			const padding = 160; // Account for padding and margins (increased for transform scaling)
			const availableWidth = containerWidth - padding;
			const newScale = (availableWidth / pageWidth) * 100;

			if (onZoomChange) {
				onZoomChange(Math.round(newScale));
			}
		}, [pageWidth, onZoomChange]);

		const scrollToPage = useCallback((pageNum) => {
			const pageElement = pagesRef.current[pageNum];
			if (pageElement && containerRef.current) {
				// Pre-render the target page and adjacent ones
				setVisiblePages(
					(prev) => new Set([...prev, pageNum - 1, pageNum, pageNum + 1]),
				);

				requestAnimationFrame(() => {
					pageElement.scrollIntoView({ behavior: "smooth", block: "start" });
				});
			}
		}, []);

		// Expose methods to parent component
		useImperativeHandle(
			ref,
			() => ({
				calculateFitToWidth,
				scrollToPage,
			}),
			[calculateFitToWidth, scrollToPage],
		);

		// Handle wheel zoom
		useEffect(() => {
			const handleWheel = (e) => {
				if (e.ctrlKey || e.metaKey) {
					e.preventDefault();

					const container = containerRef.current;
					if (!container) return;

					// Get mouse position relative to the viewport
					const rect = container.getBoundingClientRect();
					const mouseX = e.clientX - rect.left;
					const mouseY = e.clientY - rect.top;

					// Get the current scroll position
					const scrollLeft = container.scrollLeft;
					const scrollTop = container.scrollTop;

					// Calculate the actual point in the document under the mouse
					// This is the absolute position in the unscaled document
					const docX = (scrollLeft + mouseX) / scale;
					const docY = (scrollTop + mouseY) / scale;

					// Store all needed info for the scroll adjustment
					zoomPointRef.current = {
						docX,
						docY,
						mouseX,
						mouseY,
						prevScale: scale,
					};

					// Calculate new zoom
					const delta = e.deltaY > 0 ? -10 : 10;
					const newZoom = Math.max(50, Math.min(300, zoom + delta));

					if (onZoomChange) {
						setIsZooming(true);
						onZoomChange(newZoom);

						// Clear zooming state after animation
						setTimeout(() => setIsZooming(false), 300);
					}
				}
			};

			const container = containerRef.current;
			if (container) {
				container.addEventListener("wheel", handleWheel, { passive: false });
			}

			return () => {
				if (container) {
					container.removeEventListener("wheel", handleWheel);
				}
			};
		}, [zoom, onZoomChange, scale]);

		// Apply scroll adjustment after zoom changes
		useEffect(() => {
			if (zoomPointRef.current && containerRef.current) {
				const { docX, docY, mouseX, mouseY, prevScale } = zoomPointRef.current;
				const container = containerRef.current;

				// Only proceed if scale actually changed
				if (prevScale === scale) return;

				// Disable smooth scrolling temporarily
				const originalScrollBehavior = container.style.scrollBehavior;
				container.style.scrollBehavior = "auto";

				// Double RAF to ensure DOM has updated with new scale
				requestAnimationFrame(() => {
					requestAnimationFrame(() => {
						// Calculate new scroll position
						// The document point (docX, docY) should now be at position (mouseX, mouseY) in the viewport
						const newScrollLeft = docX * scale - mouseX;
						const newScrollTop = docY * scale - mouseY;

						// Apply the scroll position
						container.scrollLeft = Math.max(0, newScrollLeft);
						container.scrollTop = Math.max(0, newScrollTop);

						// Restore smooth scrolling
						setTimeout(() => {
							container.style.scrollBehavior = originalScrollBehavior;
						}, 50);

						// Clear the ref
						zoomPointRef.current = null;
					});
				});
			}
		}, [scale]);

		// Intersection Observer for efficient page visibility detection
		useEffect(() => {
			if (!numPages || !containerRef.current) return;

			const observerOptions = {
				root: containerRef.current,
				rootMargin: "200px 0px", // Pre-load pages 200px before they come into view
				threshold: 0,
			};

			const observer = new IntersectionObserver((entries) => {
				const newVisiblePages = new Set();
				let mostVisiblePage = lastValidPageRef.current; // Use last valid page instead of 1
				let maxVisibleHeight = 0;

				// First pass: collect all visible pages
				for (const entry of entries) {
					const pageNum = Number.parseInt(entry.target.dataset.page, 10);

					if (entry.isIntersecting) {
						newVisiblePages.add(pageNum);
						// Add adjacent pages for smooth scrolling
						if (pageNum > 1) newVisiblePages.add(pageNum - 1);
						if (pageNum < numPages) newVisiblePages.add(pageNum + 1);

						// Find the most visible page
						const visibleHeight = entry.intersectionRect.height;
						if (visibleHeight > maxVisibleHeight) {
							maxVisibleHeight = visibleHeight;
							mostVisiblePage = pageNum;
						}
					}
				}

				// Update visible pages if there are changes
				if (newVisiblePages.size > 0) {
					setVisiblePages((prev) => {
						// Keep existing visible pages and add new ones
						const combined = new Set([...prev, ...newVisiblePages]);

						// Remove pages that are too far away (more than 3 pages)
						const filtered = new Set();
						for (const page of combined) {
							const isNearVisible = [...newVisiblePages].some(
								(visiblePage) => Math.abs(page - visiblePage) <= 3,
							);
							if (isNearVisible) {
								filtered.add(page);
							}
						}

						return filtered;
					});
				}

				// Debounce page number updates during scrolling
				if (mostVisiblePage !== pageNumberRef.current && maxVisibleHeight > 0) {
					// Clear any existing timeout
					if (scrollTimeoutRef.current) {
						clearTimeout(scrollTimeoutRef.current);
					}

					// Set a new timeout to update the page after scrolling stabilizes
					scrollTimeoutRef.current = setTimeout(() => {
						// Double-check that this is still the most visible page
						if (mostVisiblePage > 0 && mostVisiblePage <= numPages) {
							pageNumberRef.current = mostVisiblePage;
							lastValidPageRef.current = mostVisiblePage;
							setPageNumber(mostVisiblePage);
							if (onPageChange) {
								onPageChange(mostVisiblePage);
							}
						}
					}, 100); // 100ms debounce delay
				}
			}, observerOptions);

			// Wait for next frame to ensure DOM is ready
			requestAnimationFrame(() => {
				const pageElements =
					containerRef.current?.querySelectorAll(".pdf-page-wrapper");
				if (pageElements) {
					for (const el of pageElements) {
						observer.observe(el);
					}
				}
			});

			return () => {
				observer.disconnect();
				if (scrollTimeoutRef.current) {
					clearTimeout(scrollTimeoutRef.current);
				}
			};
		}, [numPages, onPageChange]); // Remove pageNumber from deps to avoid re-creating observer

		// Add scroll event listener to detect scrolling
		useEffect(() => {
			const handleScroll = () => {
				setIsScrolling(true);

				// Clear existing timeout
				if (scrollingTimeoutRef.current) {
					clearTimeout(scrollingTimeoutRef.current);
				}

				// Set scrolling to false after scrolling stops
				scrollingTimeoutRef.current = setTimeout(() => {
					setIsScrolling(false);
				}, 150);
			};

			const container = containerRef.current;
			if (container) {
				container.addEventListener("scroll", handleScroll, { passive: true });
			}

			return () => {
				if (container) {
					container.removeEventListener("scroll", handleScroll);
				}
				if (scrollingTimeoutRef.current) {
					clearTimeout(scrollingTimeoutRef.current);
				}
			};
		}, []);

		// Removed unused page navigation functions

		return (
			<div className="pdf-viewer-container">
				<div
					className={`pdf-viewer-wrapper ${isZooming ? "is-zooming" : ""} ${isScrolling ? "is-scrolling" : ""}`}
					ref={containerRef}
				>
					<Document
						file={url}
						onLoadSuccess={onDocumentLoadSuccess}
						loading={<div className="pdf-loading">Loading PDF...</div>}
						error={<div className="pdf-error">Failed to load PDF</div>}
						className="pdf-document"
						options={documentOptions}
					>
						{numPages &&
							Array.from({ length: numPages }, (_, i) => i + 1).map(
								(pageNum) => (
									<div
										key={pageNum}
										ref={(el) => {
											if (el) pagesRef.current[pageNum] = el;
										}}
										className="pdf-page-wrapper"
										data-page={pageNum}
									>
										{visiblePages.has(pageNum) ? (
											<Page
												pageNumber={pageNum}
												className="pdf-page"
												scale={scale}
												renderTextLayer={!isScrolling} // Disable text layer during fast scrolling
												renderAnnotationLayer={false}
												onRenderError={(error) => {
													// Completely suppress AbortException warnings
													if (
														error?.name === "AbortException" ||
														error?.message?.includes("cancelled")
													) {
														return; // Silently ignore
													}
													console.warn("PDF render error:", error);
												}}
												loading={
													<div
														className="pdf-page-placeholder"
														style={{ transform: `scale(${scale})` }}
													>
														<div className="pdf-page-spinner">
															Loading page {pageNum}...
														</div>
													</div>
												}
											/>
										) : (
											<div
												className="pdf-page-placeholder"
												style={{
													minHeight: `${800 * scale}px`,
													width: pageWidth
														? `${pageWidth * scale}px`
														: `${600 * scale}px`,
												}}
											>
												<div className="pdf-page-number">Page {pageNum}</div>
											</div>
										)}
									</div>
								),
							)}
					</Document>
				</div>
			</div>
		);
	},
);

PDFViewer.displayName = "PDFViewer";

export default PDFViewer;

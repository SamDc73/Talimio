import { forwardRef, useCallback, useMemo, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import "./PDFViewer.css";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const LazyPDFViewer = forwardRef(({ url, zoom = 100 }, _ref) => {
	const [numPages, setNumPages] = useState(null);
	const [visiblePages, setVisiblePages] = useState(new Set([1, 2, 3])); // Start with first 3 pages
	const scale = zoom / 100;

	// Memoize the file prop to prevent react-pdf from re-loading
	const memoizedFile = useMemo(() => ({ url }), [url]);

	const onDocumentLoadSuccess = useCallback((pdf) => {
		console.log(`📄 [LazyPDFViewer] Document loaded: ${pdf.numPages} pages`);
		setNumPages(pdf.numPages);
	}, []);

	// Simple intersection observer to load pages as they come into view
	const pageRef = useCallback(
		(node, pageNum) => {
			if (!node) return;

			const observer = new IntersectionObserver(
				(entries) => {
					entries.forEach((entry) => {
						if (entry.isIntersecting) {
							// Load current page and adjacent ones
							setVisiblePages((prev) => {
								const newSet = new Set(prev);
								newSet.add(pageNum);
								if (pageNum > 1) newSet.add(pageNum - 1);
								if (pageNum < numPages) newSet.add(pageNum + 1);
								return newSet;
							});
						}
					});
				},
				{
					rootMargin: "500px", // Load pages 500px before they're visible
				},
			);

			observer.observe(node);
			return () => observer.disconnect();
		},
		[numPages],
	);

	return (
		<div className="pdf-viewer-container">
			<div className="pdf-viewer-wrapper">
				<Document
					file={memoizedFile}
					onLoadSuccess={onDocumentLoadSuccess}
					loading={<div className="pdf-loading">Loading PDF...</div>}
					error={<div className="pdf-error">Failed to load PDF</div>}
				>
					{numPages &&
						Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
							<div
								key={pageNum}
								className="pdf-page-wrapper"
								data-page={pageNum}
								ref={(node) => pageRef(node, pageNum)}
								style={{
									minHeight: `${800 * scale}px`, // Reserve space for unloaded pages
									display: "flex",
									alignItems: "center",
									justifyContent: "center",
								}}
							>
								{visiblePages.has(pageNum) ? (
									<Page
										pageNumber={pageNum}
										scale={scale}
										renderTextLayer={true}
										renderAnnotationLayer={false}
									/>
								) : (
									<div className="pdf-page-placeholder">
										<div>Page {pageNum}</div>
									</div>
								)}
							</div>
						))}
				</Document>
			</div>
		</div>
	);
});

LazyPDFViewer.displayName = "LazyPDFViewer";

export default LazyPDFViewer;

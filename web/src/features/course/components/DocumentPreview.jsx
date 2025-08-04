/**
 * DocumentPreview Component
 *
 * Quick preview modal for viewing document content:
 * - PDF page thumbnails and navigation
 * - URL content preview with syntax highlighting
 * - Code block highlighting for technical documents
 * - Full-screen modal with zoom capabilities
 * - Document metadata display
 * - Download and external link options
 */

import DOMPurify from "dompurify";
import {
	ChevronLeft,
	ChevronRight,
	Download,
	ExternalLink,
	Eye,
	FileText,
	Link2,
	Maximize2,
	RotateCw,
	X,
	ZoomIn,
	ZoomOut,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import DocumentStatusBadge from "./DocumentStatusBadge";

/**
 * DocumentPreviewModal - Full document preview modal
 */
const DocumentPreviewModal = ({
	document,
	isOpen,
	onClose,
	onDownload,
	onOpenExternal,
}) => {
	const [currentPage, setCurrentPage] = useState(1);
	const [zoom, setZoom] = useState(100);
	const [rotation, setRotation] = useState(0);
	const [isFullscreen, setIsFullscreen] = useState(false);
	const [contentPreview, setContentPreview] = useState(null);
	const [isLoadingPreview, setIsLoadingPreview] = useState(false);

	const modalRef = useRef(null);
	const contentRef = useRef(null);

	// Load content preview (placeholder for actual implementation)
	const loadContentPreview = useCallback(async () => {
		if (!document) return;

		setIsLoadingPreview(true);
		try {
			// This would typically make an API call to get document content/preview
			// For now, we'll simulate it
			setTimeout(() => {
				if (document.document_type === "url") {
					setContentPreview({
						type: "html",
						content: `
              <div class="prose prose-sm max-w-none">
                <h1>Document Preview</h1>
                <p>This is a preview of the document content from: <a href="${document.url}" target="_blank">${document.url}</a></p>
                <p>The full content would be displayed here in a real implementation.</p>
                <blockquote>
                  <p>This preview system will be enhanced in future updates to show actual document content, syntax highlighting for code, and interactive navigation.</p>
                </blockquote>
              </div>
            `,
					});
				} else {
					setContentPreview({
						type: "pdf",
						totalPages: 5, // Simulated page count
						thumbnails: Array.from(
							{ length: 5 },
							(_, i) =>
								`/api/v1/documents/${document.id}/pages/${i + 1}/thumbnail`,
						),
					});
				}
				setIsLoadingPreview(false);
			}, 1000);
		} catch (error) {
			console.error("Failed to load content preview:", error);
			setIsLoadingPreview(false);
		}
	}, [document]);

	// Reset state when document changes
	useEffect(() => {
		if (document) {
			setCurrentPage(1);
			setZoom(100);
			setRotation(0);
			setIsFullscreen(false);
			loadContentPreview();
		}
	}, [document, loadContentPreview]);

	// Handle keyboard shortcuts
	useEffect(() => {
		const handleKeydown = (e) => {
			if (!isOpen) return;

			switch (e.key) {
				case "Escape":
					onClose();
					break;
				case "ArrowLeft":
					if (contentPreview?.type === "pdf" && currentPage > 1) {
						setCurrentPage((prev) => prev - 1);
					}
					break;
				case "ArrowRight":
					if (
						contentPreview?.type === "pdf" &&
						currentPage < (contentPreview.totalPages || 1)
					) {
						setCurrentPage((prev) => prev + 1);
					}
					break;
				case "+":
				case "=":
					if (e.ctrlKey || e.metaKey) {
						e.preventDefault();
						setZoom((prev) => Math.min(prev + 25, 200));
					}
					break;
				case "-":
					if (e.ctrlKey || e.metaKey) {
						e.preventDefault();
						setZoom((prev) => Math.max(prev - 25, 50));
					}
					break;
				case "0":
					if (e.ctrlKey || e.metaKey) {
						e.preventDefault();
						setZoom(100);
					}
					break;
			}
		};

		document.addEventListener("keydown", handleKeydown);
		return () => document.removeEventListener("keydown", handleKeydown);
	}, [
		isOpen,
		currentPage,
		contentPreview,
		onClose,
		document.addEventListener,
		document.removeEventListener,
	]);

	// Handle fullscreen toggle
	const toggleFullscreen = () => {
		if (!document.fullscreenElement) {
			modalRef.current?.requestFullscreen();
			setIsFullscreen(true);
		} else {
			document.exitFullscreen();
			setIsFullscreen(false);
		}
	};

	if (!isOpen || !document) return null;

	const formatFileSize = (bytes) => {
		if (!bytes) return "Unknown size";
		const k = 1024;
		const sizes = ["Bytes", "KB", "MB", "GB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
	};

	const formatDate = (dateString) => {
		if (!dateString) return "Unknown";
		return new Date(dateString).toLocaleDateString();
	};

	return (
		<div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
			<div
				ref={modalRef}
				className={`bg-white rounded-lg shadow-xl overflow-hidden transition-all duration-300 ${
					isFullscreen ? "w-full h-full" : "w-[95vw] h-[90vh] max-w-6xl"
				}`}
			>
				{/* Header */}
				<div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
					<div className="flex items-center space-x-3 flex-1 min-w-0">
						{document.document_type === "url" ? (
							<Link2 className="w-6 h-6 text-green-500 flex-shrink-0" />
						) : (
							<FileText className="w-6 h-6 text-blue-500 flex-shrink-0" />
						)}
						<div className="min-w-0 flex-1">
							<h2 className="text-lg font-semibold text-gray-900 truncate">
								{document.title}
							</h2>
							<div className="flex items-center space-x-3 mt-1">
								<DocumentStatusBadge status={document.status} size="sm" />
								{document.url && (
									<span className="text-sm text-gray-600 truncate">
										{document.url}
									</span>
								)}
							</div>
						</div>
					</div>

					{/* Controls */}
					<div className="flex items-center space-x-2 flex-shrink-0 ml-4">
						{/* PDF Navigation */}
						{contentPreview?.type === "pdf" && (
							<>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setCurrentPage((prev) => Math.max(prev - 1, 1))
									}
									disabled={currentPage <= 1}
								>
									<ChevronLeft className="w-4 h-4" />
								</Button>
								<span className="text-sm text-gray-600 px-2">
									{currentPage} of {contentPreview.totalPages}
								</span>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setCurrentPage((prev) =>
											Math.min(prev + 1, contentPreview.totalPages),
										)
									}
									disabled={currentPage >= contentPreview.totalPages}
								>
									<ChevronRight className="w-4 h-4" />
								</Button>
								<div className="w-px h-6 bg-gray-300 mx-2" />
							</>
						)}

						{/* Zoom Controls */}
						<Button
							variant="outline"
							size="sm"
							onClick={() => setZoom((prev) => Math.max(prev - 25, 50))}
							disabled={zoom <= 50}
						>
							<ZoomOut className="w-4 h-4" />
						</Button>
						<span className="text-sm text-gray-600 px-2 w-12 text-center">
							{zoom}%
						</span>
						<Button
							variant="outline"
							size="sm"
							onClick={() => setZoom((prev) => Math.min(prev + 25, 200))}
							disabled={zoom >= 200}
						>
							<ZoomIn className="w-4 h-4" />
						</Button>

						{/* PDF Rotation */}
						{contentPreview?.type === "pdf" && (
							<Button
								variant="outline"
								size="sm"
								onClick={() => setRotation((prev) => (prev + 90) % 360)}
							>
								<RotateCw className="w-4 h-4" />
							</Button>
						)}

						<div className="w-px h-6 bg-gray-300 mx-2" />

						{/* Actions */}
						<Button variant="outline" size="sm" onClick={toggleFullscreen}>
							<Maximize2 className="w-4 h-4" />
						</Button>

						{onOpenExternal && document.url && (
							<Button
								variant="outline"
								size="sm"
								onClick={() => onOpenExternal(document)}
							>
								<ExternalLink className="w-4 h-4" />
							</Button>
						)}

						{onDownload && document.file_path && (
							<Button
								variant="outline"
								size="sm"
								onClick={() => onDownload(document)}
							>
								<Download className="w-4 h-4" />
							</Button>
						)}

						<Button variant="ghost" size="sm" onClick={onClose}>
							<X className="w-4 h-4" />
						</Button>
					</div>
				</div>

				{/* Content */}
				<div className="flex flex-1 h-full overflow-hidden">
					{/* Main Preview Area */}
					<div className="flex-1 flex flex-col overflow-hidden">
						<div
							ref={contentRef}
							className="flex-1 overflow-auto bg-gray-100 p-4"
							style={{ zoom: `${zoom}%` }}
						>
							{isLoadingPreview ? (
								<div className="flex items-center justify-center h-full">
									<div className="text-center">
										<div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
										<p className="text-gray-600">Loading preview...</p>
									</div>
								</div>
							) : contentPreview ? (
								contentPreview.type === "pdf" ? (
									/* PDF Preview */
									<div className="flex justify-center">
										<div
											className="bg-white shadow-lg"
											style={{ transform: `rotate(${rotation}deg)` }}
										>
											<img
												src={`/api/v1/documents/${document.id}/pages/${currentPage}`}
												alt={`Page ${currentPage} of ${document.title}`}
												className="max-w-full h-auto"
												onError={(e) => {
													// Fallback placeholder for missing page images
													e.target.src =
														"data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAwIiBoZWlnaHQ9Ijc4NCIgdmlld0JveD0iMCAwIDYwMCA3ODQiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSI2MDAiIGhlaWdodD0iNzg0IiBmaWxsPSIjRjNGNEY2Ii8+CjxyZWN0IHg9IjUwIiB5PSI1MCIgd2lkdGg9IjUwMCIgaGVpZ2h0PSI2MCIgZmlsbD0iI0U1RTdFQiIvPgo8cmVjdCB4PSI1MCIgeT0iMTQwIiB3aWR0aD0iNDAwIiBoZWlnaHQ9IjIwIiBmaWxsPSIjRDFENURLIi8+CjxyZWN0IHg9IjUwIiB5PSIxODAiIHdpZHRoPSI0NTAiIGhlaWdodD0iMjAiIGZpbGw9IiNEMUQ1REIiLz4KPHN2ZyB4PSIyNTAiIHk9IjM1MCIgd2lkdGg9IjEwMCIgaGVpZ2h0PSIxMDAiPgo8Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI0MCIgZmlsbD0iIzlDQTNBRiIvPgo8dGV4dCB4PSI1MCIgeT0iNTUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIiBmb250LXNpemU9IjE0cHgiPnt7Y3VycmVudFBhZ2V9fTwvdGV4dD4KPHN2Zz4KPHN2ZyB4PSIyMDAiIHk9IjQ4MCIgd2lkdGg9IjIwMCIgaGVpZ2h0PSIyMCI+Cjx0ZXh0IHg9IjEwMCIgeT0iMTUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiM2QjczODAiIGZvbnQtc2l6ZT0iMTJweCI+UERGIFByZXZpZXcgVW5hdmFpbGFibGU8L3RleHQ+Cjwvc3ZnPgo8L3N2Zz4=";
												}}
											/>
										</div>
									</div>
								) : (
									/* HTML/URL Preview */
									<div className="bg-white rounded-lg p-6 max-w-4xl mx-auto">
										<div
											className="prose prose-sm max-w-none"
											// biome-ignore lint/security/noDangerouslySetInnerHtml: Content is sanitized with DOMPurify
											dangerouslySetInnerHTML={{
												__html: DOMPurify.sanitize(contentPreview.content),
											}}
										/>
									</div>
								)
							) : (
								<div className="flex items-center justify-center h-full">
									<div className="text-center">
										<Eye className="w-16 h-16 text-gray-400 mx-auto mb-4" />
										<h3 className="text-lg font-medium text-gray-900 mb-2">
											Preview Unavailable
										</h3>
										<p className="text-gray-600 mb-4">
											Cannot preview this document at the moment.
										</p>
										{(onDownload || onOpenExternal) && (
											<div className="flex items-center justify-center space-x-3">
												{onDownload && document.file_path && (
													<Button onClick={() => onDownload(document)}>
														<Download className="w-4 h-4 mr-2" />
														Download
													</Button>
												)}
												{onOpenExternal && document.url && (
													<Button onClick={() => onOpenExternal(document)}>
														<ExternalLink className="w-4 h-4 mr-2" />
														Open Original
													</Button>
												)}
											</div>
										)}
									</div>
								</div>
							)}
						</div>
					</div>

					{/* Sidebar with Document Info */}
					<div className="w-80 border-l border-gray-200 bg-gray-50 overflow-auto">
						<div className="p-4 space-y-6">
							{/* Document Metadata */}
							<Card>
								<div className="p-4">
									<h3 className="text-sm font-medium text-gray-900 mb-3">
										Document Information
									</h3>
									<dl className="space-y-2 text-sm">
										<div>
											<dt className="font-medium text-gray-600">Type:</dt>
											<dd className="text-gray-900 capitalize">
												{document.document_type}
											</dd>
										</div>
										<div>
											<dt className="font-medium text-gray-600">Status:</dt>
											<dd>
												<DocumentStatusBadge
													status={document.status}
													size="sm"
												/>
											</dd>
										</div>
										{document.size && (
											<div>
												<dt className="font-medium text-gray-600">Size:</dt>
												<dd className="text-gray-900">
													{formatFileSize(document.size)}
												</dd>
											</div>
										)}
										<div>
											<dt className="font-medium text-gray-600">Added:</dt>
											<dd className="text-gray-900">
												{formatDate(document.created_at)}
											</dd>
										</div>
										{document.processed_at && (
											<div>
												<dt className="font-medium text-gray-600">
													Processed:
												</dt>
												<dd className="text-gray-900">
													{formatDate(document.processed_at)}
												</dd>
											</div>
										)}
									</dl>
								</div>
							</Card>

							{/* PDF Page Thumbnails */}
							{contentPreview?.type === "pdf" && contentPreview.thumbnails && (
								<Card>
									<div className="p-4">
										<h3 className="text-sm font-medium text-gray-900 mb-3">
											Pages ({contentPreview.totalPages})
										</h3>
										<div className="grid grid-cols-2 gap-2">
											{contentPreview.thumbnails.map((thumbnail, index) => (
												<button
													type="button"
													key={thumbnail}
													onClick={() => setCurrentPage(index + 1)}
													className={`
                            relative aspect-[3/4] bg-gray-200 rounded border-2 transition-colors
                            ${
															currentPage === index + 1
																? "border-blue-500 bg-blue-50"
																: "border-gray-300 hover:border-gray-400"
														}
                          `}
												>
													<img
														src={thumbnail}
														alt={`Page ${index + 1}`}
														className="w-full h-full object-cover rounded"
														onError={(e) => {
															e.target.style.display = "none";
														}}
													/>
													<div className="absolute bottom-1 left-1 bg-black bg-opacity-75 text-white text-xs px-1 rounded">
														{index + 1}
													</div>
												</button>
											))}
										</div>
									</div>
								</Card>
							)}

							{/* Quick Actions */}
							<Card>
								<div className="p-4">
									<h3 className="text-sm font-medium text-gray-900 mb-3">
										Actions
									</h3>
									<div className="space-y-2">
										{onDownload && document.file_path && (
											<Button
												variant="outline"
												size="sm"
												onClick={() => onDownload(document)}
												className="w-full justify-start"
											>
												<Download className="w-4 h-4 mr-2" />
												Download Document
											</Button>
										)}
										{onOpenExternal && document.url && (
											<Button
												variant="outline"
												size="sm"
												onClick={() => onOpenExternal(document)}
												className="w-full justify-start"
											>
												<ExternalLink className="w-4 h-4 mr-2" />
												Open Original URL
											</Button>
										)}
									</div>
								</div>
							</Card>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default DocumentPreviewModal;

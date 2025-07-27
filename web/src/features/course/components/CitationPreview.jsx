/**
 * CitationPreview Component
 *
 * Displays inline citations with hover previews and click actions:
 * - Inline citation numbers [1], [2], etc.
 * - Hover tooltips with document excerpts
 * - Click to view full document/section
 * - Citation sidebar for detailed sources
 * - Highlighting of relevant document sections
 */

import { ChevronRight, ExternalLink, Eye, FileText, Link2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "../../../components/tooltip";

/**
 * InlineCitation - Small clickable citation number
 */
export const InlineCitation = ({
	citationNumber,
	document,
	excerpt,
	onClick,
	className = "",
}) => {
	return (
		<Tooltip delayDuration={300}>
			<TooltipTrigger asChild>
				<button
					onClick={() => onClick?.(document, excerpt)}
					className={`
              inline-flex items-center justify-center
              w-5 h-5 text-xs font-medium
              bg-blue-100 hover:bg-blue-200 
              text-blue-700 hover:text-blue-800
              border border-blue-300 hover:border-blue-400
              rounded transition-colors cursor-pointer
              mx-0.5 align-super
              ${className}
            `}
					type="button"
				>
					{citationNumber}
				</button>
			</TooltipTrigger>
			<TooltipContent side="top" className="max-w-xs">
				<div className="space-y-2">
					<div className="flex items-center space-x-2">
						{document.document_type === "url" ? (
							<Link2 className="w-4 h-4 text-green-500" />
						) : (
							<FileText className="w-4 h-4 text-blue-500" />
						)}
						<span className="text-sm font-medium truncate">
							{document.title}
						</span>
					</div>
					{excerpt && (
						<p className="text-xs text-gray-600 line-clamp-3">"{excerpt}"</p>
					)}
					<p className="text-xs text-gray-500">Click to view full context</p>
				</div>
			</TooltipContent>
		</Tooltip>
	);
};

/**
 * CitationCard - Expanded citation view for sidebars
 */
export const CitationCard = ({
	citation,
	index,
	onViewDocument,
	onViewExcerpt,
	showActions = true,
	className = "",
}) => {
	const { document, excerpt, similarity_score } = citation;

	return (
		<Card className={`p-4 ${className}`}>
			<div className="flex items-start space-x-3">
				{/* Citation Number */}
				<div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">
					{index + 1}
				</div>

				{/* Citation Content */}
				<div className="flex-1 min-w-0">
					{/* Document Info */}
					<div className="flex items-center space-x-2 mb-2">
						{document.document_type === "url" ? (
							<Link2 className="w-4 h-4 text-green-500" />
						) : (
							<FileText className="w-4 h-4 text-blue-500" />
						)}
						<h4 className="text-sm font-medium text-gray-900 truncate">
							{document.title}
						</h4>
						{similarity_score && (
							<span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
								{Math.round(similarity_score * 100)}% match
							</span>
						)}
					</div>

					{/* Excerpt */}
					{excerpt && (
						<blockquote className="text-sm text-gray-700 border-l-3 border-blue-200 pl-3 mb-3 italic">
							"{excerpt}"
						</blockquote>
					)}

					{/* Document Metadata */}
					<div className="text-xs text-gray-500 space-y-1">
						{document.document_type === "url" && document.source_url && (
							<p className="truncate">Source: {document.source_url}</p>
						)}
						{document.crawl_date && (
							<p>
								Processed: {new Date(document.crawl_date).toLocaleDateString()}
							</p>
						)}
					</div>

					{/* Actions */}
					{showActions && (
						<div className="flex items-center space-x-2 mt-3">
							{onViewExcerpt && (
								<Button
									variant="outline"
									size="sm"
									onClick={() => onViewExcerpt(citation)}
								>
									<Eye className="w-4 h-4 mr-1" />
									View Context
								</Button>
							)}

							{onViewDocument && (
								<Button
									variant="outline"
									size="sm"
									onClick={() => onViewDocument(document)}
								>
									<ExternalLink className="w-4 h-4 mr-1" />
									Open Document
								</Button>
							)}
						</div>
					)}
				</div>
			</div>
		</Card>
	);
};

/**
 * CitationSidebar - Collapsible sidebar showing all citations
 */
export const CitationSidebar = ({
	citations = [],
	isOpen = false,
	onToggle,
	onViewDocument,
	onViewExcerpt,
	className = "",
}) => {
	return (
		<div
			className={`
      flex flex-col transition-all duration-300 ease-in-out
      ${isOpen ? "w-80" : "w-12"}
      ${className}
    `}
		>
			{/* Toggle Button */}
			<div className="flex-shrink-0 border-b border-gray-200 p-3">
				<Button
					variant="ghost"
					size="sm"
					onClick={onToggle}
					className="w-full justify-between"
				>
					{isOpen ? (
						<>
							<span className="text-sm font-medium">
								Sources ({citations.length})
							</span>
							<ChevronRight className="w-4 h-4 rotate-180" />
						</>
					) : (
						<div className="w-4 h-4 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-medium">
							{citations.length}
						</div>
					)}
				</Button>
			</div>

			{/* Citations List */}
			{isOpen && (
				<div className="flex-1 overflow-y-auto p-3 space-y-3">
					{citations.length === 0 ? (
						<div className="text-center py-8">
							<FileText className="w-8 h-8 text-gray-400 mx-auto mb-2" />
							<p className="text-sm text-gray-500">No citations available</p>
						</div>
					) : (
						citations.map((citation, index) => (
							<CitationCard
								key={`${citation.document.id}-${index}`}
								citation={citation}
								index={index}
								onViewDocument={onViewDocument}
								onViewExcerpt={onViewExcerpt}
								showActions={true}
							/>
						))
					)}
				</div>
			)}
		</div>
	);
};

/**
 * CitationModal - Full-screen modal for viewing citation context
 */
export const CitationModal = ({
	citation,
	isOpen,
	onClose,
	onViewDocument,
}) => {
	const modalRef = useRef(null);

	// Close on escape key
	useEffect(() => {
		const handleEscape = (e) => {
			if (e.key === "Escape") onClose();
		};

		if (isOpen) {
			document.addEventListener("keydown", handleEscape);
			return () => document.removeEventListener("keydown", handleEscape);
		}
	}, [isOpen, onClose]);

	if (!isOpen || !citation) return null;

	const { document: citationDocument, excerpt } = citation;

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
			<div
				ref={modalRef}
				className="bg-white rounded-lg max-w-4xl w-full mx-4 shadow-xl max-h-[90vh] overflow-hidden"
			>
				{/* Header */}
				<div className="flex items-center justify-between p-6 border-b border-gray-200">
					<div className="flex items-center space-x-3">
						{citationDocument.document_type === "url" ? (
							<Link2 className="w-6 h-6 text-green-500" />
						) : (
							<FileText className="w-6 h-6 text-blue-500" />
						)}
						<div>
							<h2 className="text-lg font-semibold text-gray-900">
								{citationDocument.title}
							</h2>
							{citationDocument.source_url && (
								<p className="text-sm text-gray-600 truncate">
									{citationDocument.source_url}
								</p>
							)}
						</div>
					</div>

					<div className="flex items-center space-x-2">
						{onViewDocument && (
							<Button
								variant="outline"
								onClick={() => onViewDocument(citationDocument)}
							>
								<ExternalLink className="w-4 h-4 mr-2" />
								Open Document
							</Button>
						)}
						<Button variant="ghost" onClick={onClose}>
							×
						</Button>
					</div>
				</div>

				{/* Content */}
				<div className="p-6 overflow-y-auto max-h-[70vh]">
					<div className="prose prose-sm max-w-none">
						<h3 className="text-base font-medium text-gray-900 mb-4">
							Relevant Excerpt
						</h3>

						{excerpt ? (
							<blockquote className="text-gray-700 border-l-4 border-blue-200 pl-4 py-2 bg-blue-50 rounded-r">
								"{excerpt}"
							</blockquote>
						) : (
							<p className="text-gray-500 italic">
								No specific excerpt available. This document was referenced in
								the context.
							</p>
						)}

						{/* Document Metadata */}
						<div className="mt-6 p-4 bg-gray-50 rounded-lg">
							<h4 className="text-sm font-medium text-gray-900 mb-2">
								Document Information
							</h4>
							<dl className="grid grid-cols-2 gap-2 text-sm">
								<dt className="font-medium text-gray-600">Type:</dt>
								<dd className="text-gray-900 capitalize">
									{citationDocument.document_type}
								</dd>

								<dt className="font-medium text-gray-600">Status:</dt>
								<dd className="text-gray-900 capitalize">
									{citationDocument.status}
								</dd>

								{citationDocument.crawl_date && (
									<>
										<dt className="font-medium text-gray-600">Processed:</dt>
										<dd className="text-gray-900">
											{new Date(
												citationDocument.crawl_date,
											).toLocaleDateString()}
										</dd>
									</>
								)}
							</dl>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

/**
 * Helper function to parse text with inline citations
 * Converts [1], [2] patterns to InlineCitation components
 */
export const parseCitationsInText = (text, citations = [], onCitationClick) => {
	if (!text || citations.length === 0) return text;

	// Regular expression to find citation patterns like [1], [2], etc.
	const citationRegex = /\[(\d+)\]/g;
	const parts = [];
	let lastIndex = 0;
	let match = citationRegex.exec(text);

	while (match !== null) {
		const citationNumber = parseInt(match[1], 10);
		const citation = citations[citationNumber - 1]; // Arrays are 0-indexed

		// Add text before citation
		if (match.index > lastIndex) {
			parts.push(text.slice(lastIndex, match.index));
		}

		// Add citation component
		if (citation) {
			parts.push(
				<InlineCitation
					key={`citation-${citationNumber}-${match.index}`}
					citationNumber={citationNumber}
					document={citation.document}
					excerpt={citation.excerpt}
					onClick={onCitationClick}
				/>,
			);
		} else {
			// Fallback for missing citations
			parts.push(`[${citationNumber}]`);
		}

		lastIndex = match.index + match[0].length;
		match = citationRegex.exec(text);
	}

	// Add remaining text
	if (lastIndex < text.length) {
		parts.push(text.slice(lastIndex));
	}

	return parts;
};

export default {
	InlineCitation,
	CitationCard,
	CitationSidebar,
	CitationModal,
	parseCitationsInText,
};

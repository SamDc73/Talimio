/**
 * DocumentList Component
 *
 * Displays and manages a list of documents for a course:
 * - Shows document status with badges
 * - Supports sorting and filtering
 * - Document removal with confirmation
 * - Search functionality
 * - Download/view options
 * - Pagination for large lists
 */

import {
	ArrowDown,
	ArrowUp,
	Calendar,
	Download,
	Eye,
	FileText,
	Filter,
	Link2,
	MoreVertical,
	Search,
	Trash2,
} from "lucide-react"
import { useMemo, useState } from "react"
import { Button } from "@/components/Button"
import { Card } from "@/components/Card"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/DropdownMenu"
import { Input } from "@/components/Input"
import { isDocumentFailed, isDocumentProcessing, isDocumentReady } from "../utils/documentUtils"
import DocumentStatusBadge, { DocumentStatusSummary } from "./DocumentStatusBadge"

function DocumentList({
	documents = [],
	onRemoveDocument,
	onViewDocument,
	onDownloadDocument,
	isLoading = false,
	emptyMessage = "No documents uploaded yet",
	showActions = true,
	showSearch = true,
	showFilter = true,
	showSorting = true,
	className = "",
}) {
	const [searchTerm, setSearchTerm] = useState("")
	const [statusFilter, setStatusFilter] = useState("all")
	const [sortBy, setSortBy] = useState("created_at")
	const [sortOrder, setSortOrder] = useState("desc")

	// Filter and sort documents
	const filteredDocuments = useMemo(() => {
		let filtered = documents

		// Apply search filter
		if (searchTerm.trim()) {
			const search = searchTerm.toLowerCase()
			filtered = filtered.filter(
				(doc) =>
					doc.title?.toLowerCase().includes(search) ||
					doc.document_type?.toLowerCase().includes(search) ||
					doc.url?.toLowerCase().includes(search)
			)
		}

		// Apply status filter
		if (statusFilter !== "all") {
			filtered = filtered.filter((doc) => {
				switch (statusFilter) {
					case "ready": {
						return isDocumentReady(doc)
					}
					case "processing": {
						return isDocumentProcessing(doc)
					}
					case "failed": {
						return isDocumentFailed(doc)
					}
					default: {
						return true
					}
				}
			})
		}

		// Apply sorting
		filtered.sort((a, b) => {
			let aValue = a[sortBy]
			let bValue = b[sortBy]

			// Handle date sorting
			if (sortBy.includes("_at")) {
				aValue = new Date(aValue)
				bValue = new Date(bValue)
			}

			// Handle string sorting
			if (typeof aValue === "string" && typeof bValue === "string") {
				aValue = aValue.toLowerCase()
				bValue = bValue.toLowerCase()
			}

			if (sortOrder === "asc") {
				return aValue > bValue ? 1 : -1
			}
			return aValue < bValue ? 1 : -1
		})

		return filtered
	}, [documents, searchTerm, statusFilter, sortBy, sortOrder])

	// Get file type icon
	const getFileTypeIcon = (doc) => {
		if (doc.document_type === "url") {
			return <Link2 className="size-5  text-green-500" />
		}
		return <FileText className="size-5  text-blue-500" />
	}

	// Format file size
	const formatFileSize = (bytes) => {
		if (!bytes) return "Unknown size"
		const k = 1024
		const sizes = ["Bytes", "KB", "MB", "GB"]
		const i = Math.floor(Math.log(bytes) / Math.log(k))
		return `${Number.parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`
	}

	// Format date
	const formatDate = (dateString) => {
		if (!dateString) return "Unknown"
		return new Date(dateString).toLocaleDateString()
	}

	// Handle sort change
	const handleSort = (field) => {
		if (sortBy === field) {
			setSortOrder(sortOrder === "asc" ? "desc" : "asc")
		} else {
			setSortBy(field)
			setSortOrder("desc")
		}
	}

	// Get sort icon
	const getSortIcon = (field) => {
		if (sortBy !== field) return null
		return sortOrder === "asc" ? <ArrowUp className="size-4 " /> : <ArrowDown className="size-4 " />
	}
	let emptyStateContent = emptyMessage
	if (searchTerm || statusFilter !== "all") {
		emptyStateContent = (
			<div className="p-8 text-center">
				<FileText className="size-12  text-muted-foreground/70 mx-auto mb-4" />
				<p className="text-muted-foreground mb-2">No documents match your criteria</p>
				<Button
					variant="outline"
					size="sm"
					onClick={() => {
						setSearchTerm("")
						setStatusFilter("all")
					}}
				>
					Clear filters
				</Button>
			</div>
		)
	} else if (typeof emptyMessage === "string") {
		emptyStateContent = (
			<div className="p-8 text-center">
				<FileText className="size-12  text-muted-foreground/70 mx-auto mb-4" />
				<p className="text-muted-foreground mb-2">{emptyMessage}</p>
			</div>
		)
	}

	if (isLoading) {
		return (
			<Card className={className}>
				<div className="p-6 text-center">
					<div className="animate-spin rounded-full size-8  border-b-2 border-blue-600 mx-auto mb-4" />
					<p className="text-muted-foreground">Loading documents...</p>
				</div>
			</Card>
		)
	}

	return (
		<div className={className}>
			{/* Header with controls */}
			<div className="mb-4 space-y-4">
				{/* Summary */}
				<div className="flex items-center justify-between">
					<DocumentStatusSummary documents={documents} />
					{documents.length > 0 && (
						<span className="text-sm text-muted-foreground/80">
							{filteredDocuments.length} of {documents.length} documents
						</span>
					)}
				</div>

				{/* Search and Filter Controls */}
				{(showSearch || showFilter) && documents.length > 0 && (
					<div className="flex flex-col sm:flex-row gap-3">
						{/* Search */}
						{showSearch && (
							<div className="flex-1 relative">
								<Search className="absolute left-3 top-1/2 transform -translate-y-1/2 size-4  text-muted-foreground/70" />
								<Input
									type="text"
									placeholder="Search documents..."
									value={searchTerm}
									onChange={(e) => setSearchTerm(e.target.value)}
									className="pl-10"
								/>
							</div>
						)}

						{/* Filter */}
						{showFilter && (
							<div className="flex items-center space-x-2">
								<Filter className="size-4  text-muted-foreground/70" />
								<select
									value={statusFilter}
									onChange={(e) => setStatusFilter(e.target.value)}
									className="px-3 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
								>
									<option value="all">All Status</option>
									<option value="ready">Ready</option>
									<option value="processing">Processing</option>
									<option value="failed">Failed</option>
								</select>
							</div>
						)}
					</div>
				)}
			</div>

			{/* Document List */}
			{filteredDocuments.length === 0 ? (
				<Card>{emptyStateContent}</Card>
			) : (
				<Card>
					<div className="overflow-hidden">
						{/* Sort Header */}
						{showSorting && (
							<div className="px-6 py-3 bg-muted/40 border-b border-border text-sm font-medium text-foreground">
								<div className="grid grid-cols-12 gap-4">
									<div className="col-span-5">
										<button
											type="button"
											onClick={() => handleSort("title")}
											className="flex items-center space-x-1 hover:text-foreground"
										>
											<span>Document</span>
											{getSortIcon("title")}
										</button>
									</div>
									<div className="col-span-2">
										<button
											type="button"
											onClick={() => handleSort("document_type")}
											className="flex items-center space-x-1 hover:text-foreground"
										>
											<span>Type</span>
											{getSortIcon("document_type")}
										</button>
									</div>
									<div className="col-span-2">
										<button
											type="button"
											onClick={() => handleSort("status")}
											className="flex items-center space-x-1 hover:text-foreground"
										>
											<span>Status</span>
											{getSortIcon("status")}
										</button>
									</div>
									<div className="col-span-2">
										<button
											type="button"
											onClick={() => handleSort("created_at")}
											className="flex items-center space-x-1 hover:text-foreground"
										>
											<span>Date</span>
											{getSortIcon("created_at")}
										</button>
									</div>
									{showActions && <div className="col-span-1 text-right">Actions</div>}
								</div>
							</div>
						)}

						{/* Document Items */}
						<div className="divide-y divide-border">
							{filteredDocuments.map((doc) => (
								<div key={doc.id} className="px-6 py-4 hover:bg-muted/40">
									<div className="grid grid-cols-12 gap-4 items-center">
										{/* Document Info */}
										<div className="col-span-5">
											<div className="flex items-center space-x-3">
												<div className="shrink-0">{getFileTypeIcon(doc)}</div>
												<div className="min-w-0 flex-1">
													<p className="text-sm font-medium text-foreground truncate">
														{doc.title || "Untitled Document"}
													</p>
													{doc.document_type === "url" && doc.url && (
														<p className="text-xs text-muted-foreground/80 truncate">{doc.url}</p>
													)}
													{doc.file_path && doc.size > 0 && (
														<p className="text-xs text-muted-foreground/80">{formatFileSize(doc.size)}</p>
													)}
												</div>
											</div>
										</div>

										{/* Type */}
										<div className="col-span-2">
											<span className="text-sm text-muted-foreground capitalize">{doc.document_type || "Unknown"}</span>
										</div>

										{/* Status */}
										<div className="col-span-2">
											<DocumentStatusBadge status={doc.status} size="sm" />
										</div>

										{/* Date */}
										<div className="col-span-2">
											<div className="flex items-center text-sm text-muted-foreground/80">
												<Calendar className="size-4  mr-1" />
												{formatDate(doc.created_at)}
											</div>
										</div>

										{/* Actions */}
										{showActions && (
											<div className="col-span-1 text-right">
												<DropdownMenu>
													<DropdownMenuTrigger asChild>
														<Button variant="ghost" size="sm">
															<MoreVertical className="size-4 " />
														</Button>
													</DropdownMenuTrigger>
													<DropdownMenuContent align="end">
														{isDocumentReady(doc) && onViewDocument && (
															<DropdownMenuItem onClick={() => onViewDocument(doc)}>
																<Eye className="size-4  mr-2" />
																View
															</DropdownMenuItem>
														)}
														{doc.file_path && onDownloadDocument && (
															<DropdownMenuItem onClick={() => onDownloadDocument(doc)}>
																<Download className="size-4  mr-2" />
																Download
															</DropdownMenuItem>
														)}
														{onRemoveDocument && (
															<DropdownMenuItem
																onClick={() => onRemoveDocument(doc)}
																className="text-red-600 hover:text-red-800"
															>
																<Trash2 className="size-4  mr-2" />
																Remove
															</DropdownMenuItem>
														)}
													</DropdownMenuContent>
												</DropdownMenu>
											</div>
										)}
									</div>
								</div>
							))}
						</div>
					</div>
				</Card>
			)}
		</div>
	)
}

export default DocumentList

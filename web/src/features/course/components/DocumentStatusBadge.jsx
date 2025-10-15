/**
 * DocumentStatusBadge Component
 *
 * Displays the processing status of documents with appropriate colors and icons:
 * - pending: Gray with clock icon
 * - processing: Blue with spinner
 * - embedded/ready: Green with check icon
 * - failed: Red with error icon
 *
 * Supports hover tooltips and different sizes.
 */

import { AlertCircle, CheckCircle2, Clock, Loader2 } from "lucide-react"

function DocumentStatusBadge({ status, size = "default", showIcon = true, showText = true, className = "" }) {
	// Status configuration
	const statusConfig = {
		pending: {
			label: "Pending",
			color: "bg-muted text-foreground border-border",
			icon: Clock,
			description: "Document is queued for processing",
		},
		processing: {
			label: "Processing",
			color: "bg-accent/15 text-accent-foreground border-accent/30",
			icon: Loader2,
			description: "Document is being processed and chunked",
			animated: true,
		},
		embedded: {
			label: "Ready",
			color: "bg-primary/15 text-primary border-primary/30",
			icon: CheckCircle2,
			description: "Document is ready and searchable",
		},
		failed: {
			label: "Failed",
			color: "bg-destructive/15 text-destructive border-destructive/30",
			icon: AlertCircle,
			description: "Document processing failed",
		},
	}

	// Size configurations
	const sizeConfig = {
		sm: {
			container: "px-2 py-1 text-xs",
			icon: "w-3 h-3",
			gap: "gap-1",
		},
		default: {
			container: "px-2.5 py-1.5 text-sm",
			icon: "w-4 h-4",
			gap: "gap-1.5",
		},
		lg: {
			container: "px-3 py-2 text-base",
			icon: "w-5 h-5",
			gap: "gap-2",
		},
	}

	const config = statusConfig[status] || statusConfig.pending
	const sizes = sizeConfig[size]
	const Icon = config.icon

	return (
		<span
			className={`
        inline-flex items-center rounded-full border font-medium
        ${config.color}
        ${sizes.container}
        ${sizes.gap}
        ${className}
      `}
			title={config.description}
		>
			{showIcon && (
				<Icon
					className={`
            ${sizes.icon}
            ${config.animated ? "animate-spin" : ""}
          `}
				/>
			)}
			{showText && config.label}
		</span>
	)
}

/**
 * DocumentStatusIndicator - Minimalist version for tight spaces
 */
export function DocumentStatusIndicator({ status, className = "" }) {
	const statusConfig = {
		pending: "bg-muted-foreground/60",
		processing: "bg-accent animate-pulse",
		embedded: "bg-primary",
		failed: "bg-destructive",
	}

	const color = statusConfig[status] || statusConfig.pending

	return <div className={`w-2 h-2 rounded-full ${color} ${className}`} title={status} />
}

/**
 * DocumentStatusProgress - Progress bar version for processing states
 */
export function DocumentStatusProgress({ status, progress = null, className = "" }) {
	const isProcessing = status === "processing"
	const progressValue = progress !== null ? progress : isProcessing ? 50 : 0

	return (
		<div className={`space-y-1 ${className}`}>
			<div className="flex items-center justify-between text-sm">
				<DocumentStatusBadge status={status} size="sm" />
				{isProcessing && progress !== null && <span className="text-xs text-muted-foreground/80">{progress}%</span>}
			</div>

			{(isProcessing || status === "embedded") && (
				<div className="w-full bg-muted/40 rounded-full h-1.5">
					<div
						className={`h-1.5 rounded-full transition-all duration-300 ${
							status === "embedded" ? "bg-primary" : "bg-accent"
						} ${isProcessing && progress === null ? "animate-pulse" : ""}`}
						style={{
							width: status === "embedded" ? "100%" : `${progressValue}%`,
						}}
					/>
				</div>
			)}
		</div>
	)
}

/**
 * DocumentStatusSummary - Shows aggregated status for multiple documents
 */
export function DocumentStatusSummary({ documents, className = "" }) {
	const counts = documents.reduce((acc, doc) => {
		acc[doc.status] = (acc[doc.status] || 0) + 1
		return acc
	}, {})

	const total = documents.length
	const ready = counts.embedded || 0
	const processing = (counts.processing || 0) + (counts.pending || 0)
	const failed = counts.failed || 0

	if (total === 0) {
		return <div className={`text-sm text-muted-foreground/80 ${className}`}>No documents</div>
	}

	return (
		<div className={`flex items-center space-x-2 text-sm ${className}`}>
			<span className="font-medium">
				{total} document{total !== 1 ? "s" : ""}
			</span>
			<span className="text-muted-foreground/70">•</span>

			{ready > 0 && (
				<>
					<span className="text-primary">{ready} ready</span>
					{(processing > 0 || failed > 0) && <span className="text-muted-foreground/70">•</span>}
				</>
			)}

			{processing > 0 && (
				<>
					<span className="text-accent">{processing} processing</span>
					{failed > 0 && <span className="text-muted-foreground/70">•</span>}
				</>
			)}

			{failed > 0 && <span className="text-destructive">{failed} failed</span>}
		</div>
	)
}

export default DocumentStatusBadge

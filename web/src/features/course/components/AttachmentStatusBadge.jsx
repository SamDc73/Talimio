/**
 * AttachmentStatusBadge Component
 *
 * Displays the embedding status of an attached book's RAG pipeline:
 * - pending: queued for embedding
 * - processing: embedding in progress
 * - completed: searchable
 * - failed: embedding failed
 */

import { AlertCircle, CheckCircle2, Clock, Loader2 } from "lucide-react"

const STATUS_CONFIG = {
	pending: {
		label: "Pending",
		color: "bg-muted text-foreground border-border",
		icon: Clock,
		description: "Book is queued for embedding",
	},
	processing: {
		label: "Processing",
		color: "bg-accent/15 text-accent-foreground border-accent/30",
		icon: Loader2,
		description: "Book is being embedded",
		animated: true,
	},
	completed: {
		label: "Ready",
		color: "bg-primary/15 text-primary border-primary/30",
		icon: CheckCircle2,
		description: "Book is searchable in this course",
	},
	failed: {
		label: "Failed",
		color: "bg-destructive/15 text-destructive border-destructive/30",
		icon: AlertCircle,
		description: "Book embedding failed",
	},
}

function AttachmentStatusBadge({ ragStatus, className = "" }) {
	const config = STATUS_CONFIG[ragStatus] || STATUS_CONFIG.pending
	const Icon = config.icon

	return (
		<span
			title={config.description}
			className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${config.color} ${className}`}
		>
			<Icon className={`size-3.5 ${config.animated ? "animate-spin" : ""}`} />
			{config.label}
		</span>
	)
}

export default AttachmentStatusBadge

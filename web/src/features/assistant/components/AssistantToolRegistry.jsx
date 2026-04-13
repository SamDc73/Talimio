import { CheckCircle2Icon, CircleAlertIcon, ExternalLinkIcon } from "lucide-react"
import { Badge } from "@/components/Badge"
import { Button } from "@/components/Button"

const TOOL_STATUS_STYLES = {
	complete: {
		icon: CheckCircle2Icon,
		iconClassName: "text-completed",
	},
	"requires-action": {
		icon: CircleAlertIcon,
		iconClassName: "text-due-today",
	},
	incomplete: {
		icon: CircleAlertIcon,
		iconClassName: "text-destructive",
	},
}

const CONFIRMATION_BADGE_CLASS_NAME = "rounded-md border-due-today/30 bg-due-today/10 px-2 py-1 text-due-today-text"

const normalizeUiItems = (result) => {
	if (!result || typeof result !== "object") {
		return []
	}
	if (!Array.isArray(result.toolUi)) {
		return []
	}
	return result.toolUi.filter((item) => item && typeof item === "object")
}

const resolveStatus = (status, result) => {
	if (result?.status === "confirmation_required") {
		return "requires-action"
	}
	const type = status?.type
	if (type === "incomplete") {
		return "incomplete"
	}
	if (type === "requires-action") {
		return "requires-action"
	}
	return "complete"
}

const renderConfirmationText = (item) => {
	const title = typeof item.title === "string" ? item.title : "Confirmation required"
	const message = typeof item.message === "string" && item.message ? `: ${item.message}` : ""
	const actionName = typeof item.actionName === "string" && item.actionName ? ` (${item.actionName})` : ""
	const labels =
		typeof item.confirmLabel === "string" && typeof item.cancelLabel === "string"
			? ` [${item.confirmLabel}/${item.cancelLabel}]`
			: ""
	return `${title}${message}${actionName}${labels}`
}

const renderToolUiItem = (item, uiItemKey) => {
	if (item.type === "link" && typeof item.href === "string") {
		return (
			<Button key={uiItemKey(item)} variant="outline" size="sm" asChild>
				<a href={item.href} rel="noreferrer">
					{typeof item.label === "string" ? item.label : "Open"}
					<ExternalLinkIcon className="size-3.5" />
				</a>
			</Button>
		)
	}
	if (item.type === "confirmation") {
		return (
			<Badge key={uiItemKey(item)} variant="outline" className={CONFIRMATION_BADGE_CLASS_NAME}>
				{renderConfirmationText(item)}
			</Badge>
		)
	}
	return null
}

export function LearningCapabilityToolCard({ toolName, result, status }) {
	const toolStatus = resolveStatus(status, result)
	const { icon: StatusIcon, iconClassName } = TOOL_STATUS_STYLES[toolStatus]
	const message = typeof result?.message === "string" ? result.message : ""
	const uiItems = normalizeUiItems(result)
	const uiItemKey = (item) => {
		if (item.type === "link" && typeof item.href === "string") {
			return `${toolName}-link-${item.href}`
		}
		if (item.type === "confirmation" && typeof item.title === "string") {
			return `${toolName}-confirmation-${item.title}`
		}
		return `${toolName}-${JSON.stringify(item)}`
	}

	return (
		<div className="mb-3 flex w-full flex-col gap-2 rounded-lg border border-border/70 bg-card px-3 py-2">
			<div className="flex items-center gap-2 text-sm">
				<StatusIcon className={`size-4 ${iconClassName}`} />
				<span className="font-medium text-foreground">{toolName}</span>
			</div>
			{message ? <p className="text-muted-foreground text-sm">{message}</p> : null}
			{uiItems.length > 0 ? (
				<div className="flex flex-wrap items-center gap-2">
					{uiItems.map((item) => renderToolUiItem(item, uiItemKey))}
				</div>
			) : null}
		</div>
	)
}

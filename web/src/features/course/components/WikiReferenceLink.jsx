import * as PopoverPrimitive from "@radix-ui/react-popover"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { Popover, PopoverContent } from "@/components/Popover"
import { cn } from "@/lib/utils"

const WIKIPEDIA_SUMMARY_STALE_TIME_MS = 60 * 60 * 1000
const HOVER_OPEN_DELAY_MS = 250
const HOVER_CLOSE_DELAY_MS = 120

function getWikipediaPageUrl(wikiKey) {
	return `https://en.wikipedia.org/wiki/${encodeURIComponent(wikiKey)}`
}

function supportsHoverPreview() {
	if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
		return false
	}

	return window.matchMedia("(hover: hover) and (pointer: fine)").matches
}

async function fetchWikipediaSummary({ queryKey, signal }) {
	const [, wikiKey] = queryKey
	if (!wikiKey) {
		throw new Error("Wikipedia key is required")
	}

	const response = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(wikiKey)}`, {
		headers: { Accept: "application/json" },
		signal,
	})

	if (!response.ok) {
		throw new Error(`Wikipedia preview request failed: ${response.status}`)
	}

	const payload = await response.json()
	if (!payload || typeof payload !== "object") {
		throw new Error("Wikipedia preview response was invalid")
	}

	const pageUrl = payload.content_urls?.desktop?.page
	const thumbnailUrl = payload.thumbnail?.source
	const title =
		typeof payload.title === "string" && payload.title.trim() ? payload.title.trim() : wikiKey.replaceAll("_", " ")
	const summary = typeof payload.extract === "string" ? payload.extract.trim() : ""
	const normalizedThumbnailUrl = typeof thumbnailUrl === "string" && thumbnailUrl.trim() ? thumbnailUrl.trim() : null
	const normalizedPageUrl =
		typeof pageUrl === "string" && pageUrl.trim() ? pageUrl.trim() : getWikipediaPageUrl(wikiKey)

	return {
		title,
		summary,
		thumbnailUrl: normalizedThumbnailUrl,
		pageUrl: normalizedPageUrl,
	}
}

function getInlineLabel(children) {
	if (Array.isArray(children)) {
		return children
			.map((child) => (typeof child === "string" ? child : ""))
			.join("")
			.trim()
	}

	if (typeof children === "string") {
		return children.trim()
	}

	return "Wikipedia reference"
}

function renderPopoverBody({ data, error, isPending, wikiKey }) {
	if (isPending) {
		return (
			<div className="space-y-3 p-4" role="status">
				<div className="h-5 w-1/2 animate-pulse rounded-md bg-muted" />
				<div className="space-y-2">
					<div className="h-4 w-full animate-pulse rounded-md bg-muted" />
					<div className="h-4 w-5/6 animate-pulse rounded-md bg-muted" />
				</div>
			</div>
		)
	}

	if (error) {
		return (
			<div className="flex flex-col gap-2 p-4 text-sm text-muted-foreground">
				<p>Preview unavailable right now.</p>
				<a
					href={getWikipediaPageUrl(wikiKey)}
					target="_blank"
					rel="noreferrer"
					className="inline-flex w-fit items-center text-xs font-medium text-primary hover:underline"
				>
					Open Wikipedia directly
					<svg aria-hidden="true" className="ml-1 size-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2}
							d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
						/>
					</svg>
				</a>
			</div>
		)
	}

	if (!data) {
		return null
	}

	return (
		<div className="flex flex-col">
			{data.thumbnailUrl ? (
				<div className="relative h-36 w-full shrink-0 bg-muted/30">
					<img src={data.thumbnailUrl} alt={data.title} className="absolute inset-0 size-full object-cover" />
					<div className="absolute inset-0 bg-linear-to-t from-background via-background/40 to-transparent" />
				</div>
			) : null}

			<div className={cn("flex flex-col p-5", data.thumbnailUrl ? "pt-0 -mt-4 relative z-10" : "")}>
				<h4 className="mb-2 text-lg font-semibold tracking-tight text-foreground flex items-center gap-2">
					{data.title}
				</h4>
				{data.summary ? <p className="mb-5 text-sm/relaxed text-muted-foreground">{data.summary}</p> : null}

				<div className="mt-auto">
					<a
						href={data.pageUrl}
						target="_blank"
						rel="noreferrer"
						className="inline-flex items-center rounded-md bg-secondary/60 px-3 py-1.5 text-xs font-medium text-secondary-foreground transition-colors hover:bg-secondary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
					>
						Read on Wikipedia
						<svg aria-hidden="true" className="ml-1.5 size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
							/>
						</svg>
					</a>
				</div>
			</div>
		</div>
	)
}

export function WikiReferenceLink({ children, className, href, node, ...buttonProps }) {
	const wikiKey = typeof href === "string" ? href.slice("wiki:".length).trim() : ""
	const label = getInlineLabel(children)
	const triggerRef = useRef(null)
	const contentRef = useRef(null)
	const openTimerRef = useRef(null)
	const closeTimerRef = useRef(null)
	const [open, setOpen] = useState(false)

	const { data, error, isPending } = useQuery({
		queryKey: ["wikipedia-summary", wikiKey],
		queryFn: fetchWikipediaSummary,
		enabled: open && Boolean(wikiKey),
		staleTime: WIKIPEDIA_SUMMARY_STALE_TIME_MS,
		retry: 1,
	})

	useEffect(() => {
		return () => {
			if (openTimerRef.current !== null) {
				window.clearTimeout(openTimerRef.current)
			}

			if (closeTimerRef.current !== null) {
				window.clearTimeout(closeTimerRef.current)
			}
		}
	}, [])

	if (!wikiKey) {
		return <span>{children}</span>
	}

	const clearTimer = (timerRef) => {
		if (timerRef.current !== null) {
			window.clearTimeout(timerRef.current)
			timerRef.current = null
		}
	}

	const cancelScheduledOpen = () => {
		clearTimer(openTimerRef)
	}

	const cancelScheduledClose = () => {
		clearTimer(closeTimerRef)
	}

	const openPopover = () => {
		cancelScheduledOpen()
		cancelScheduledClose()
		setOpen(true)
	}

	const scheduleOpen = () => {
		if (open || openTimerRef.current !== null) {
			cancelScheduledClose()
			return
		}

		cancelScheduledClose()
		openTimerRef.current = window.setTimeout(() => {
			setOpen(true)
			openTimerRef.current = null
		}, HOVER_OPEN_DELAY_MS)
	}

	const scheduleClose = () => {
		cancelScheduledOpen()
		cancelScheduledClose()
		closeTimerRef.current = window.setTimeout(() => {
			setOpen(false)
			closeTimerRef.current = null
		}, HOVER_CLOSE_DELAY_MS)
	}

	const handleClick = (event) => {
		event.preventDefault()

		if (supportsHoverPreview()) {
			return
		}

		cancelScheduledOpen()
		cancelScheduledClose()
		setOpen((currentOpen) => !currentOpen)
	}

	const handlePointerEnter = (event) => {
		if (event.pointerType && event.pointerType !== "mouse") {
			return
		}

		if (!supportsHoverPreview()) {
			return
		}

		scheduleOpen()
	}

	const handlePointerLeave = (event) => {
		if (event.pointerType && event.pointerType !== "mouse") {
			return
		}

		if (!supportsHoverPreview()) {
			return
		}

		scheduleClose()
	}

	const handleBlur = (event) => {
		const nextFocusedElement = event.relatedTarget

		if (
			nextFocusedElement instanceof Node &&
			(triggerRef.current?.contains(nextFocusedElement) || contentRef.current?.contains(nextFocusedElement))
		) {
			return
		}

		scheduleClose()
	}

	return (
		<Popover
			open={open}
			onOpenChange={(nextOpen) => {
				cancelScheduledOpen()
				cancelScheduledClose()
				setOpen(nextOpen)
			}}
		>
			<PopoverPrimitive.Anchor asChild>
				<button
					ref={triggerRef}
					type="button"
					onBlur={handleBlur}
					onClick={handleClick}
					onFocus={openPopover}
					onPointerEnter={handlePointerEnter}
					onPointerLeave={handlePointerLeave}
					className={cn(
						"inline cursor-pointer appearance-none rounded-[0.25rem] px-[0.15rem] py-0.5 font-medium text-primary underline decoration-primary/40 decoration-dashed underline-offset-4 transition-all hover:bg-primary/10 hover:decoration-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-1",
						className
					)}
					aria-expanded={open}
					aria-haspopup="dialog"
					aria-label={`Learn more about ${label} on Wikipedia`}
					{...buttonProps}
				>
					{children}
				</button>
			</PopoverPrimitive.Anchor>
			<PopoverContent
				ref={contentRef}
				align="center"
				sideOffset={4}
				className="w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-border/50 bg-background p-0 shadow-2xl duration-200 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
				onBlur={handleBlur}
				onFocus={openPopover}
				onPointerEnter={handlePointerEnter}
				onPointerLeave={handlePointerLeave}
			>
				{renderPopoverBody({ data, error, isPending, wikiKey })}
			</PopoverContent>
		</Popover>
	)
}

// biome-ignore lint/style/useComponentExportOnlyModules: this file keeps the named and default component export together for existing MDX imports.
export default WikiReferenceLink

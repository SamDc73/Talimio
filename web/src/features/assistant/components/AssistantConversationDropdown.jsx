import { ThreadListItemPrimitive, ThreadListPrimitive, useAuiState } from "@assistant-ui/react"
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu"
import { ChevronDownIcon, TrashIcon } from "lucide-react"
import { createContext, useCallback, useContext, useRef, useState } from "react"
import { cn } from "@/lib/utils"

const DEFAULT_THREAD_TITLE = "New chat"

const ConversationDropdownCloseContext = createContext(() => {})

function useConversationDropdownClose() {
	return useContext(ConversationDropdownCloseContext)
}

function ConversationThreadListItem() {
	const closeDropdown = useConversationDropdownClose()

	return (
		<ThreadListItemPrimitive.Root className="group flex items-center gap-1 rounded-lg px-1 py-0.5 data-[active=true]:bg-primary/10 data-[active=true]:text-primary">
			<ThreadListItemPrimitive.Trigger asChild>
				<button
					type="button"
					onClick={closeDropdown}
					data-thread-nav="true"
					className="flex min-w-0 flex-1 items-center rounded-md px-2 py-2 text-left text-sm hover:bg-accent/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
				>
					<span className="truncate">
						<ThreadListItemPrimitive.Title fallback={DEFAULT_THREAD_TITLE} />
					</span>
				</button>
			</ThreadListItemPrimitive.Trigger>

			<ThreadListItemPrimitive.Delete asChild>
				<button
					type="button"
					onClick={closeDropdown}
					className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
					aria-label="Delete conversation"
				>
					<TrashIcon className="size-4" />
				</button>
			</ThreadListItemPrimitive.Delete>
		</ThreadListItemPrimitive.Root>
	)
}

export function AssistantConversationDropdown() {
	const [open, setOpen] = useState(false)
	const contentRef = useRef(null)
	const regularThreadCount = useAuiState((state) => state.threads.threadIds.length)
	const activeThreadTitle = useAuiState((state) => {
		const { mainThreadId, newThreadId, threadItems } = state.threads
		if (newThreadId && mainThreadId === newThreadId) {
			return DEFAULT_THREAD_TITLE
		}

		const activeThread = threadItems.find((threadItem) => threadItem.id === mainThreadId)
		if (!activeThread?.title) {
			return DEFAULT_THREAD_TITLE
		}

		return activeThread.title
	})

	const closeDropdown = useCallback(() => {
		setOpen(false)
	}, [])

	const focusableNavSelector = "[data-thread-nav='true']:not([disabled])"

	const focusFirstThreadButton = useCallback(() => {
		const firstButton = contentRef.current?.querySelector(focusableNavSelector)
		if (firstButton instanceof HTMLButtonElement) {
			firstButton.focus()
		}
	}, [])

	const handleListNavigation = useCallback((event) => {
		if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
			return
		}

		const focusableButtons = [...(contentRef.current?.querySelectorAll(focusableNavSelector) || [])]
		if (focusableButtons.length === 0) {
			return
		}

		event.preventDefault()

		const currentIndex = focusableButtons.indexOf(document.activeElement)
		const offset = event.key === "ArrowDown" ? 1 : -1
		if (currentIndex === -1) {
			const initialIndex = offset > 0 ? 0 : focusableButtons.length - 1
			focusableButtons[initialIndex]?.focus()
			return
		}

		const nextIndex = (currentIndex + offset + focusableButtons.length) % focusableButtons.length
		focusableButtons[nextIndex]?.focus()
	}, [])

	if (regularThreadCount === 0) {
		return (
			<div className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-foreground">
				<span className="max-w-[200px] truncate">{activeThreadTitle}</span>
			</div>
		)
	}

	return (
		<ConversationDropdownCloseContext.Provider value={closeDropdown}>
			<DropdownMenuPrimitive.Root open={open} onOpenChange={setOpen}>
				<DropdownMenuPrimitive.Trigger asChild>
					<button
						type="button"
						className={cn(
							"group flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors outline-none",
							"hover:bg-accent/50 focus-visible:ring-2 focus-visible:ring-ring/20",
							"data-[state=open]:bg-accent/50"
						)}
						aria-label="Conversation list"
					>
						<span className="max-w-[200px] truncate text-foreground group-hover:text-accent-foreground/90 transition-colors">
							{activeThreadTitle}
						</span>
						<ChevronDownIcon
							className={cn(
								"size-3.5 text-muted-foreground/70 transition-transform duration-200",
								open && "rotate-180"
							)}
						/>
					</button>
				</DropdownMenuPrimitive.Trigger>

				<DropdownMenuPrimitive.Content
					ref={contentRef}
					align="start"
					side="bottom"
					sideOffset={8}
					onKeyDown={handleListNavigation}
					onOpenAutoFocus={(event) => {
						event.preventDefault()
						focusFirstThreadButton()
					}}
					className="z-50 w-[280px] overflow-hidden rounded-xl border border-border/40 bg-popover/95 backdrop-blur-xl p-1.5 text-popover-foreground shadow-xl data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
				>
					<div className="max-h-[300px] overflow-y-auto px-0.5">
						<div className="flex flex-col gap-0.5">
							<ThreadListPrimitive.Items components={{ ThreadListItem: ConversationThreadListItem }} />
						</div>
					</div>
				</DropdownMenuPrimitive.Content>
			</DropdownMenuPrimitive.Root>
		</ConversationDropdownCloseContext.Provider>
	)
}

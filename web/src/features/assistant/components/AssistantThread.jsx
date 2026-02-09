import {
	ActionBarPrimitive,
	BranchPickerPrimitive,
	ComposerPrimitive,
	ErrorPrimitive,
	MessagePrimitive,
	ThreadPrimitive,
} from "@assistant-ui/react"
import { domAnimation, LazyMotion, MotionConfig, motion as m } from "framer-motion"
import {
	ArrowDownIcon,
	ArrowUpIcon,
	CheckIcon,
	ChevronLeftIcon,
	ChevronRightIcon,
	CopyIcon,
	PencilIcon,
	RefreshCwIcon,
	Square,
	X,
} from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "@/components/Button"
import { useChatSidebar } from "@/contexts/ChatSidebarContext"
import {
	ComposerAddAttachment,
	ComposerAttachments,
	UserMessageAttachments,
} from "@/features/assistant/components/AssistantAttachment"
import { MarkdownText } from "@/features/assistant/components/MarkdownText"
import { ModelPicker } from "@/features/assistant/components/ModelPicker"
import { ToolFallback } from "@/features/assistant/components/ToolFallback"
import { TooltipIconButton } from "@/features/assistant/components/TooltipIconButton"
import logger from "@/lib/logger"
import { cn } from "@/lib/utils"

export function AssistantThread() {
	return (
		<LazyMotion features={domAnimation}>
			<MotionConfig reducedMotion="user">
				<ThreadPrimitive.Root
					className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
					style={{
						"--thread-max-width": "42rem",
					}}
				>
					<ThreadPrimitive.Viewport className="aui-thread-viewport relative flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-3 pt-2">
						<ThreadWelcome />
						<ThreadPrimitive.Messages
							components={{
								UserMessage,
								EditComposer,
								AssistantMessage,
							}}
						/>
						<ThreadPrimitive.If empty={false}>
							<div className="aui-thread-viewport-spacer min-h-4 grow" />
						</ThreadPrimitive.If>
						<Composer />
					</ThreadPrimitive.Viewport>
				</ThreadPrimitive.Root>
			</MotionConfig>
		</LazyMotion>
	)
}

function ComposerAction() {
	const { initialText, setPendingQuote } = useChatSidebar()
	return (
		<div className="aui-composer-action-wrapper relative mx-2 mb-1.5 mt-0.5 flex items-center justify-between">
			<div className="flex items-center gap-1.5">
				<ComposerAddAttachment />
				<ModelPicker className="h-7" />
			</div>

			<ThreadPrimitive.If running={false}>
				<ComposerPrimitive.Send asChild>
					<TooltipIconButton
						tooltip="Send message"
						side="bottom"
						type="submit"
						variant="default"
						size="icon"
						className="aui-composer-send size-7 rounded-full p-0 shadow-[0_1px_2px_rgba(0,0,0,0.1)] transition-all duration-150 hover:scale-105 hover:shadow-[0_2px_4px_rgba(0,0,0,0.15)] active:scale-95"
						onClick={() => {
							if (initialText) setPendingQuote(initialText)
						}}
						aria-label="Send message"
					>
						<ArrowUpIcon className="aui-composer-send-icon size-4" />
					</TooltipIconButton>
				</ComposerPrimitive.Send>
			</ThreadPrimitive.If>

			<ThreadPrimitive.If running>
				<ComposerPrimitive.Cancel asChild>
					<Button
						type="button"
						variant="default"
						size="icon"
						className="aui-composer-cancel size-7 rounded-full p-0 transition-all duration-150 hover:scale-105 active:scale-95"
						aria-label="Stop generating"
					>
						<Square className="aui-composer-cancel-icon size-3 fill-white dark:fill-black" />
					</Button>
				</ComposerPrimitive.Cancel>
			</ThreadPrimitive.If>
		</div>
	)
}

function MessageError() {
	return (
		<MessagePrimitive.Error>
			<ErrorPrimitive.Root className="aui-message-error-root mt-1.5 rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-2 text-[13px] leading-normal text-destructive/90 dark:border-destructive/15 dark:bg-destructive/10">
				<ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
			</ErrorPrimitive.Root>
		</MessagePrimitive.Error>
	)
}

function AssistantMessage() {
	return (
		<MessagePrimitive.Root asChild>
			<div
				className="aui-assistant-message-root relative mx-auto flex w-full max-w-(--thread-max-width) flex-col items-start gap-1 py-2.5 pl-2 duration-200 first:pt-1.5 last:mb-16"
				data-role="assistant"
			>
				<div className="aui-assistant-message-content max-w-[min(75%,520px)] wrap-break-word text-[15px] leading-[1.6] tracking-[-0.011em] text-foreground/95">
					<MessagePrimitive.Parts
						components={{
							Text: MarkdownText,
							tools: { Fallback: ToolFallback },
						}}
					/>
					<MessageError />
				</div>

				<div className="aui-assistant-message-footer absolute right-2 top-1/2 -translate-y-1/2 flex">
					<BranchPicker />
					<AssistantActionBar />
				</div>
			</div>
		</MessagePrimitive.Root>
	)
}

function ThreadWelcome() {
	return (
		<ThreadPrimitive.Empty>
			<div className="aui-thread-welcome-root mx-auto mt-12 mb-auto flex w-full max-w-(--thread-max-width) grow flex-col">
				<div className="aui-thread-welcome-center flex w-full grow flex-col items-center justify-center">
					<div className="aui-thread-welcome-message flex size-full flex-col justify-center px-4">
						<m.div
							initial={{ opacity: 0, y: 8 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: 8 }}
							className="aui-thread-welcome-message-motion-1 text-[22px] font-semibold tracking-[-0.015em]"
						>
							Hello there!
						</m.div>
						<m.div
							initial={{ opacity: 0, y: 8 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: 8 }}
							transition={{ delay: 0.08 }}
							className="aui-thread-welcome-message-motion-2 text-[22px] tracking-[-0.015em] text-muted-foreground/60"
						>
							How can I help you today?
						</m.div>
					</div>
				</div>
			</div>
		</ThreadPrimitive.Empty>
	)
}

function ThreadScrollToBottom() {
	return (
		<ThreadPrimitive.ScrollToBottom asChild>
			<TooltipIconButton
				tooltip="Scroll to bottom"
				variant="outline"
				className="aui-thread-scroll-to-bottom absolute -top-11 z-10 size-8 self-center rounded-full border-border/60 bg-background/95 p-0 shadow-[0_2px_8px_rgba(0,0,0,0.08)] backdrop-blur-xl transition-all duration-150 hover:scale-105 hover:shadow-[0_4px_12px_rgba(0,0,0,0.12)] disabled:invisible dark:border-border/40 dark:bg-background/90"
			>
				<ArrowDownIcon className="size-4 " />
			</TooltipIconButton>
		</ThreadPrimitive.ScrollToBottom>
	)
}

function Composer() {
	const { initialText: replyText, setInitialText, setPendingQuote } = useChatSidebar()
	useEffect(() => {
		// Keep pendingQuote in sync ONLY when we have a non-empty selection.
		// This avoids wiping pendingQuote when runtime clears initialText on send.
		if (replyText) {
			setPendingQuote(replyText)
		}
	}, [replyText, setPendingQuote])
	return (
		<div className="aui-composer-wrapper sticky bottom-0 mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-3 overflow-visible rounded-t-3xl bg-background pb-3 md:pb-4">
			<ThreadScrollToBottom />
			<ComposerPrimitive.Root className="aui-composer-root group relative flex w-full flex-col rounded-2xl border border-border/60 bg-background/95 shadow-[0_2px_8px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.06)] backdrop-blur-xl transition-all duration-200 hover:border-border hover:shadow-[0_4px_16px_rgba(0,0,0,0.06),0_2px_4px_rgba(0,0,0,0.08)] dark:border-border/40 dark:bg-background/90 dark:shadow-[0_2px_8px_rgba(0,0,0,0.2),0_1px_2px_rgba(0,0,0,0.15)] dark:hover:border-border/60">
				<ComposerAttachments />
				{replyText && (
					<div className="aui-composer-reply group/quote relative mx-2 mb-1.5 mt-2 rounded-xl border border-primary/15 bg-primary/2.5 backdrop-blur-sm dark:border-primary/10 dark:bg-primary/4">
						<div className="flex items-start gap-2 px-3 py-1.5">
							<blockquote className="relative flex-1 min-w-0 pl-2.5 text-[13px] leading-normal text-foreground/70 before:absolute before:left-0 before:top-0.5 before:bottom-0.5 before:w-[1.5px] before:rounded-full before:bg-primary/40 dark:before:bg-primary/30">
								<span className="max-h-[4.2rem] overflow-hidden whitespace-pre-wrap wrap-break-word [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:3]">
									{replyText}
								</span>
							</blockquote>
							<button
								type="button"
								className="mt-px flex size-4  shrink-0 items-center justify-center rounded-sm text-muted-foreground/40 opacity-0 transition-all hover:bg-primary/10 hover:text-foreground/60 focus-visible:opacity-100 group-hover/quote:opacity-100"
								onClick={() => {
									setInitialText("")
									logger.info("cleared selection quote")
								}}
								aria-label="Clear selection quote"
							>
								<X className="size-2.5 " />
							</button>
						</div>
					</div>
				)}
				<ComposerPrimitive.Input
					placeholder="Send a message..."
					className="aui-composer-input mx-2 mb-1 max-h-32 min-h-[52px] w-auto resize-none bg-transparent p-1   text-[15px] leading-normal tracking-[-0.011em] text-foreground outline-none placeholder:text-muted-foreground/50"
					rows={1}
					autoFocus
					aria-label="Message input"
					spellCheck="true"
				/>
				<ComposerAction />
			</ComposerPrimitive.Root>
		</div>
	)
}

function AssistantActionBar() {
	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root col-start-3 row-start-2 -ml-0.5 flex gap-0.5 text-muted-foreground/60 data-floating:absolute data-floating:rounded-lg data-floating:border data-floating:border-border/60 data-floating:bg-background/95 data-floating:p-0.5 data-floating:shadow-[0_2px_8px_rgba(0,0,0,0.08)] data-floating:backdrop-blur-xl"
		>
			<ActionBarPrimitive.Copy asChild>
				<TooltipIconButton tooltip="Copy" className="size-7 ">
					<MessagePrimitive.If copied>
						<CheckIcon className="size-3.5 " />
					</MessagePrimitive.If>
					<MessagePrimitive.If copied={false}>
						<CopyIcon className="size-3.5 " />
					</MessagePrimitive.If>
				</TooltipIconButton>
			</ActionBarPrimitive.Copy>
			<ActionBarPrimitive.Reload asChild>
				<TooltipIconButton tooltip="Refresh" className="size-7 ">
					<RefreshCwIcon className="size-3.5 " />
				</TooltipIconButton>
			</ActionBarPrimitive.Reload>
		</ActionBarPrimitive.Root>
	)
}

function UserMessage() {
	const { claimPendingQuote } = useChatSidebar()
	const [quotedAtSend] = useState(() => claimPendingQuote())

	return (
		<MessagePrimitive.Root asChild>
			<div
				className="aui-user-message-root relative mx-auto flex w-full max-w-(--thread-max-width) flex-col items-end gap-1 py-2.5 pr-2 duration-200 first:pt-1.5 last:mb-5"
				data-role="user"
			>
				<UserMessageAttachments />

				{quotedAtSend && (
					<div className="aui-user-message-quote max-w-[min(75%,520px)] rounded-2xl border border-primary/15 bg-primary/2.5 px-3 py-1.5 text-[13px] leading-normal text-foreground/70 backdrop-blur-sm dark:border-primary/10 dark:bg-primary/4">
						<blockquote className="relative pl-2.5 before:absolute before:left-0 before:top-0.5 before:bottom-0.5 before:w-[1.5px] before:rounded-full before:bg-primary/40 dark:before:bg-primary/30">
							<span className="max-h-[4.2rem] overflow-hidden whitespace-pre-wrap wrap-break-word [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:3]">
								{quotedAtSend}
							</span>
						</blockquote>
					</div>
				)}

				<div className="aui-user-message-content max-w-[min(75%,520px)] rounded-[1.25rem] bg-muted/90 px-3.5 py-1.5 text-[15px] leading-normal tracking-[-0.011em] text-foreground/95 backdrop-blur-sm">
					<MessagePrimitive.Parts
						components={{
							Text: MarkdownText,
						}}
					/>
				</div>

				<div className="aui-user-action-bar absolute left-2 top-1/2 -translate-y-1/2">
					<UserActionBar />
				</div>

				<BranchPicker />
			</div>
		</MessagePrimitive.Root>
	)
}

function UserActionBar() {
	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			className="aui-user-action-bar-root flex flex-col items-end"
		>
			<ActionBarPrimitive.Edit asChild>
				<TooltipIconButton tooltip="Edit" className="aui-user-action-edit size-7  text-muted-foreground/60">
					<PencilIcon className="size-3.5 " />
				</TooltipIconButton>
			</ActionBarPrimitive.Edit>
		</ActionBarPrimitive.Root>
	)
}

function EditComposer() {
	return (
		<MessagePrimitive.Root asChild>
			<div className="aui-edit-composer-wrapper mx-auto flex w-full max-w-(--thread-max-width) flex-col items-end py-2.5 pr-2 first:pt-2.5">
				<ComposerPrimitive.Root className="aui-edit-composer-root flex w-full max-w-[min(75%,520px)] flex-col rounded-2xl border border-border/60 bg-background/95 shadow-[0_2px_8px_rgba(0,0,0,0.04)] backdrop-blur-xl dark:border-border/40 dark:bg-background/90 dark:shadow-[0_2px_8px_rgba(0,0,0,0.2)]">
					<ComposerPrimitive.Input
						className="aui-edit-composer-input min-h-[52px] w-full resize-none bg-transparent px-3.5 py-2 text-[15px] leading-normal tracking-[-0.011em] text-foreground outline-none"
						autoFocus
						spellCheck="true"
					/>

					<div className="aui-edit-composer-footer mx-2 mb-2 flex items-center justify-end gap-1.5">
						<ComposerPrimitive.Cancel asChild>
							<Button variant="ghost" size="sm" className="h-7 text-[13px]" aria-label="Cancel edit">
								Cancel
							</Button>
						</ComposerPrimitive.Cancel>
						<ComposerPrimitive.Send asChild>
							<Button
								size="sm"
								className="h-7 text-[13px] shadow-[0_1px_2px_rgba(0,0,0,0.1)]"
								aria-label="Update message"
							>
								Update
							</Button>
						</ComposerPrimitive.Send>
					</div>
				</ComposerPrimitive.Root>
			</div>
		</MessagePrimitive.Root>
	)
}

function BranchPicker({ className, ...rest }) {
	return (
		<BranchPickerPrimitive.Root
			hideWhenSingleBranch
			className={cn(
				"aui-branch-picker-root mr-1 -ml-1 inline-flex items-center gap-0.5 text-[11px] text-muted-foreground/60",
				className
			)}
			{...rest}
		>
			<BranchPickerPrimitive.Previous asChild>
				<TooltipIconButton tooltip="Previous" className="size-6 ">
					<ChevronLeftIcon className="size-3 " />
				</TooltipIconButton>
			</BranchPickerPrimitive.Previous>
			<span className="aui-branch-picker-state px-1 font-medium tabular-nums">
				<BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
			</span>
			<BranchPickerPrimitive.Next asChild>
				<TooltipIconButton tooltip="Next" className="size-6 ">
					<ChevronRightIcon className="size-3 " />
				</TooltipIconButton>
			</BranchPickerPrimitive.Next>
		</BranchPickerPrimitive.Root>
	)
}

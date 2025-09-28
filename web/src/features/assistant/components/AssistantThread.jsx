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
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
	ComposerAddAttachment,
	ComposerAttachments,
	UserMessageAttachments,
} from "@/features/assistant/components/AssistantAttachment"
import { MarkdownText } from "@/features/assistant/components/MarkdownText"
import { ModelPicker } from "@/features/assistant/components/ModelPicker"
import { ToolFallback } from "@/features/assistant/components/ToolFallback"
import { TooltipIconButton } from "@/features/assistant/components/TooltipIconButton"
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
					<ThreadPrimitive.Viewport className="aui-thread-viewport relative flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-4 pt-2">
						<ThreadWelcome />

						<ThreadPrimitive.Messages
							components={{
								UserMessage,
								EditComposer,
								AssistantMessage,
							}}
						/>
						<ThreadPrimitive.If empty={false}>
							<div className="aui-thread-viewport-spacer min-h-8 grow" />
						</ThreadPrimitive.If>
						<Composer />
					</ThreadPrimitive.Viewport>
				</ThreadPrimitive.Root>
			</MotionConfig>
		</LazyMotion>
	)
}

function ThreadScrollToBottom() {
	return (
		<ThreadPrimitive.ScrollToBottom asChild>
			<TooltipIconButton
				tooltip="Scroll to bottom"
				variant="outline"
				className="aui-thread-scroll-to-bottom absolute -top-12 z-10 self-center rounded-full p-4 disabled:invisible dark:bg-background dark:hover:bg-accent"
			>
				<ArrowDownIcon />
			</TooltipIconButton>
		</ThreadPrimitive.ScrollToBottom>
	)
}

function ThreadWelcome() {
	return (
		<ThreadPrimitive.Empty>
			<div className="aui-thread-welcome-root mx-auto mt-8 mb-auto flex w-full max-w-[var(--thread-max-width)] flex-grow flex-col">
				<div className="aui-thread-welcome-center flex w-full flex-grow flex-col items-center justify-center">
					<div className="aui-thread-welcome-message flex size-full flex-col justify-center px-6">
						<m.div
							initial={{ opacity: 0, y: 10 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: 10 }}
							className="aui-thread-welcome-message-motion-1 text-2xl font-semibold"
						>
							Hello there!
						</m.div>
						<m.div
							initial={{ opacity: 0, y: 10 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: 10 }}
							transition={{ delay: 0.1 }}
							className="aui-thread-welcome-message-motion-2 text-2xl text-muted-foreground/65"
						>
							How can I help you today?
						</m.div>
					</div>
				</div>
			</div>
		</ThreadPrimitive.Empty>
	)
}

function Composer() {
	return (
		<div className="aui-composer-wrapper sticky bottom-0 mx-auto flex w-full max-w-[var(--thread-max-width)] flex-col gap-4 overflow-visible rounded-t-3xl bg-background pb-4 md:pb-6">
			<ThreadScrollToBottom />
			<ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col rounded-3xl border border-border bg-muted px-1 pt-2 shadow-[0_9px_9px_0px_rgba(0,0,0,0.01),0_2px_5px_0px_rgba(0,0,0,0.06)] dark:border-muted-foreground/15">
				<ComposerAttachments />
				<ComposerPrimitive.Input
					placeholder="Send a message..."
					className="aui-composer-input mb-1 max-h-32 min-h-16 w-full resize-none bg-transparent px-3.5 pt-1.5 pb-3 text-base outline-none placeholder:text-muted-foreground focus:outline-primary"
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

function ComposerAction() {
	return (
		<div className="aui-composer-action-wrapper relative mx-1 mt-2 mb-2 flex items-center justify-between">
			<div className="flex items-center gap-2">
				<ComposerAddAttachment />
				<ModelPicker className="h-8" />
			</div>

			<ThreadPrimitive.If running={false}>
				<ComposerPrimitive.Send asChild>
					<TooltipIconButton
						tooltip="Send message"
						side="bottom"
						type="submit"
						variant="default"
						size="icon"
						className="aui-composer-send size-[34px] rounded-full p-1"
						aria-label="Send message"
					>
						<ArrowUpIcon className="aui-composer-send-icon size-5" />
					</TooltipIconButton>
				</ComposerPrimitive.Send>
			</ThreadPrimitive.If>

			<ThreadPrimitive.If running>
				<ComposerPrimitive.Cancel asChild>
					<Button
						type="button"
						variant="default"
						size="icon"
						className="aui-composer-cancel size-[34px] rounded-full border border-muted-foreground/60 hover:bg-primary/75 dark:border-muted-foreground/90"
						aria-label="Stop generating"
					>
						<Square className="aui-composer-cancel-icon size-3.5 fill-white dark:fill-black" />
					</Button>
				</ComposerPrimitive.Cancel>
			</ThreadPrimitive.If>
		</div>
	)
}

function MessageError() {
	return (
		<MessagePrimitive.Error>
			<ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive dark:bg-destructive/5 dark:text-red-200">
				<ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
			</ErrorPrimitive.Root>
		</MessagePrimitive.Error>
	)
}

function AssistantMessage() {
	return (
		<MessagePrimitive.Root asChild>
			<div
				className="aui-assistant-message-root relative mx-auto w-full max-w-[var(--thread-max-width)] animate-in py-4 duration-200 fade-in slide-in-from-bottom-1 last:mb-16 first:pt-2"
				data-role="assistant"
			>
				<div className="aui-assistant-message-content mx-2 leading-7 break-words text-foreground">
					<MessagePrimitive.Parts
						components={{
							Text: MarkdownText,
							tools: { Fallback: ToolFallback },
						}}
					/>
					<MessageError />
				</div>

				<div className="aui-assistant-message-footer mt-2 ml-2 flex">
					<BranchPicker />
					<AssistantActionBar />
				</div>
			</div>
		</MessagePrimitive.Root>
	)
}

function AssistantActionBar() {
	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root col-start-3 row-start-2 -ml-1 flex gap-1 text-muted-foreground data-floating:absolute data-floating:rounded-md data-floating:border data-floating:bg-background data-floating:p-1 data-floating:shadow-sm"
		>
			<ActionBarPrimitive.Copy asChild>
				<TooltipIconButton tooltip="Copy">
					<MessagePrimitive.If copied>
						<CheckIcon />
					</MessagePrimitive.If>
					<MessagePrimitive.If copied={false}>
						<CopyIcon />
					</MessagePrimitive.If>
				</TooltipIconButton>
			</ActionBarPrimitive.Copy>
			<ActionBarPrimitive.Reload asChild>
				<TooltipIconButton tooltip="Refresh">
					<RefreshCwIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.Reload>
		</ActionBarPrimitive.Root>
	)
}

function UserMessage() {
	return (
		<MessagePrimitive.Root asChild>
			<div
				className="aui-user-message-root mx-auto grid w-full max-w-[var(--thread-max-width)] animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] gap-y-2 px-2 py-4 duration-200 fade-in slide-in-from-bottom-1 first:pt-2 last:mb-5 [&:where(>*)]:col-start-2"
				data-role="user"
			>
				<UserMessageAttachments />

				<div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
					<div className="aui-user-message-content rounded-3xl bg-muted px-5 py-2.5 break-words text-foreground">
						<MessagePrimitive.Parts />
					</div>
					<div className="aui-user-action-bar-wrapper absolute top-1/2 left-0 -translate-x-full -translate-y-1/2 pr-2">
						<UserActionBar />
					</div>
				</div>

				<BranchPicker className="aui-user-branch-picker col-span-full col-start-1 row-start-3 -mr-1 justify-end" />
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
				<TooltipIconButton tooltip="Edit" className="aui-user-action-edit p-4">
					<PencilIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.Edit>
		</ActionBarPrimitive.Root>
	)
}

function EditComposer() {
	return (
		<div className="aui-edit-composer-wrapper mx-auto flex w-full max-w-[var(--thread-max-width)] flex-col gap-4 px-2 first:mt-4">
			<ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-7/8 flex-col rounded-xl bg-muted">
				<ComposerPrimitive.Input
					className="aui-edit-composer-input flex min-h-[60px] w-full resize-none bg-transparent p-4 text-foreground outline-none"
					autoFocus
					spellCheck="true"
				/>

				<div className="aui-edit-composer-footer mx-3 mb-3 flex items-center justify-center gap-2 self-end">
					<ComposerPrimitive.Cancel asChild>
						<Button variant="ghost" size="sm" aria-label="Cancel edit">
							Cancel
						</Button>
					</ComposerPrimitive.Cancel>
					<ComposerPrimitive.Send asChild>
						<Button size="sm" aria-label="Update message">
							Update
						</Button>
					</ComposerPrimitive.Send>
				</div>
			</ComposerPrimitive.Root>
		</div>
	)
}

function BranchPicker({ className, ...rest }) {
	return (
		<BranchPickerPrimitive.Root
			hideWhenSingleBranch
			className={cn(
				"aui-branch-picker-root mr-2 -ml-2 inline-flex items-center text-xs text-muted-foreground",
				className
			)}
			{...rest}
		>
			<BranchPickerPrimitive.Previous asChild>
				<TooltipIconButton tooltip="Previous">
					<ChevronLeftIcon />
				</TooltipIconButton>
			</BranchPickerPrimitive.Previous>
			<span className="aui-branch-picker-state font-medium">
				<BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
			</span>
			<BranchPickerPrimitive.Next asChild>
				<TooltipIconButton tooltip="Next">
					<ChevronRightIcon />
				</TooltipIconButton>
			</BranchPickerPrimitive.Next>
		</BranchPickerPrimitive.Root>
	)
}

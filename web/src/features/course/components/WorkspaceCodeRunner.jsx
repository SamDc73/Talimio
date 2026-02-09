import CodeMirror from "@uiw/react-codemirror"
import { AlertTriangle, CheckCircle, FileText, Play, RotateCcw } from "lucide-react"
import { Button } from "@/components/Button"
import ErrorBoundary from "@/components/ErrorBoundary"
import { useCodeMirrorLanguageExtensions } from "@/features/course/hooks/use-code-mirror-language"
import { useWorkspaceExecutionState } from "@/features/course/hooks/use-workspace-execution-state"
import { useWorkspaceState } from "@/features/course/hooks/use-workspace-registry"
import { cn } from "@/lib/utils"
import { catppuccinLatteColors } from "./catppuccinTheme"

const LATTE_BORDER_COLOR = catppuccinLatteColors.surface1.hex

export default function WorkspaceCodeRunner({ workspaceId, lessonId, courseId }) {
	const { workspace, files } = useWorkspaceState(workspaceId)

	const {
		files: editableFiles,
		activeFile,
		activePath,
		onSelectFile,
		onCodeChange,
		onRun,
		onReset,
		result,
		error,
		isRunning,
		canReset,
	} = useWorkspaceExecutionState({ workspaceId, lessonId, courseId, files })

	const editorExtensions = useCodeMirrorLanguageExtensions(activeFile?.language)
	const workspaceLabel = workspace?.label || "Workspace"

	if (!workspace || editableFiles.length === 0) {
		return null
	}

	return (
		<div
			className="relative group mb-8 rounded-xl overflow-hidden border bg-card shadow-sm"
			style={{ borderColor: LATTE_BORDER_COLOR }}
		>
			<div
				className="flex flex-col gap-2 border-b bg-linear-to-r from-slate-100/60 via-muted/45 to-muted/25 px-4 py-3"
				style={{ borderBottomColor: LATTE_BORDER_COLOR }}
			>
				<div className="flex flex-wrap items-center justify-between gap-3">
					<div>
						<p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary/80">Workspace</p>
						<p className="text-lg font-semibold text-foreground">{workspaceLabel}</p>
					</div>
					<div className="inline-flex items-center rounded-full border border-border/80 bg-background/80 shadow-xs">
						<Button
							type="button"
							onClick={onRun}
							disabled={isRunning}
							variant="outline"
							size="sm"
							className="rounded-s-full border-transparent"
						>
							<Play className="size-4 " />
							<span>{isRunning ? "Running" : "Run workspace"}</span>
						</Button>
						<Button
							type="button"
							onClick={onReset}
							disabled={!canReset}
							variant="outline"
							size="sm"
							className="rounded-e-full border-transparent"
						>
							{canReset ? <RotateCcw className="size-4 " /> : <CheckCircle className="size-4 " />}
							<span>{canReset ? "Reset" : "Synced"}</span>
						</Button>
					</div>
				</div>
				<p className="text-sm text-muted-foreground/90">Edit any file, then run all of them together in one sandbox.</p>
			</div>
			<div className="grid gap-0 md:grid-cols-[230px_1fr]">
				<div className="border-r border-border/60 bg-muted/20 p-3 space-y-2">
					{editableFiles.map((file) => {
						const isActive = file.filePath === activePath
						return (
							<button
								key={file.filePath}
								type="button"
								onClick={() => onSelectFile(file.filePath)}
								className={cn(
									"w-full rounded-lg border px-3 py-2 text-left transition-all",
									isActive
										? "border-primary/60 bg-primary/10 text-foreground"
										: "border-transparent bg-white/60 text-muted-foreground hover:border-border"
								)}
							>
								<div className="flex items-center gap-2 text-sm font-medium">
									<FileText className="size-4 " />
									<span className="truncate">{file.filePath}</span>
								</div>
								{file.isEntry && (
									<p className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-primary">Entry file</p>
								)}
							</button>
						)
					})}
				</div>
				<div className="p-4">
					<ErrorBoundary>
						<CodeMirror
							value={activeFile?.code || ""}
							onChange={(value) => activeFile?.filePath && onCodeChange(activeFile.filePath, value)}
							basicSetup={{ lineNumbers: false, foldGutter: false }}
							className="bg-transparent"
							style={{ fontSize: "0.9rem", lineHeight: 1.6 }}
							extensions={editorExtensions}
						/>
					</ErrorBoundary>
				</div>
			</div>
			{(result || error) && (
				<div className="border-t border-border bg-muted/20 p-4  space-y-3">
					{error && (
						<div className="rounded-md border p-3 bg-destructive/10 border-l-2 border-l-destructive">
							<div className="flex items-center gap-2 text-xs font-semibold text-destructive mb-2">
								<AlertTriangle className="size-4 " />
								Error
							</div>
							<pre className="text-xs font-mono whitespace-pre-wrap text-destructive/90">{error}</pre>
						</div>
					)}
					{result?.stdout && (
						<div className="rounded-md border p-3 bg-emerald-50 border-l-2 border-l-emerald-500">
							<div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 mb-2">
								<CheckCircle className="size-4 " />
								Output
							</div>
							<pre className="text-xs font-mono whitespace-pre-wrap text-foreground/90">{result.stdout}</pre>
						</div>
					)}
					{result?.stderr && (
						<div className="rounded-md border p-3 bg-amber-50 border-l-2 border-l-amber-500">
							<div className="flex items-center gap-2 text-xs font-semibold text-amber-700 mb-2">
								<AlertTriangle className="size-4 " />
								Warnings
							</div>
							<pre className="text-xs font-mono whitespace-pre-wrap text-amber-900">{result.stderr}</pre>
						</div>
					)}
				</div>
			)}
		</div>
	)
}

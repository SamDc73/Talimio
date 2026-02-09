/**
 * Personalization Dialog Component for AI customization
 */

import { ArrowLeft, ChevronRight, Loader2, Plus, Server, Sparkles, Trash2, X, Zap } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import {
	clearUserMemory,
	createMcpServer,
	deleteMcpServer,
	deleteMemory,
	getUserMemories,
	getUserSettings,
	listMcpServers,
	updateCustomInstructions,
} from "@/api/personalizationApi"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import logger from "@/lib/logger"
import { cn } from "@/lib/utils"

const createEmptyServerForm = () => ({
	url: "",
	authType: "none",
	authToken: "",
})

let headerRowCounter = 0

const createHeaderRow = () => ({
	id:
		typeof crypto !== "undefined" && crypto.randomUUID
			? crypto.randomUUID()
			: `header-${Date.now()}-${headerRowCounter++}`,
	key: "",
	value: "",
})

// View states for the dialog
const VIEW = {
	MAIN: "main",
	MEMORIES: "memories",
	MCP: "mcp",
	MCP_ADD: "mcp_add",
}

export function PersonalizationDialog({ open, onOpenChange }) {
	const [view, setView] = useState(VIEW.MAIN)
	const [isLoading, setIsLoading] = useState(false)
	const [isSaving, setIsSaving] = useState(false)
	const [isClearing, setIsClearing] = useState(false)
	const [instructions, setInstructions] = useState("")
	const [memoryCount, setMemoryCount] = useState(0)
	const [originalInstructions, setOriginalInstructions] = useState("")
	const [memories, setMemories] = useState([])
	const [isLoadingMemories, setIsLoadingMemories] = useState(false)
	const [mcpServers, setMcpServers] = useState([])
	const [isLoadingServers, setIsLoadingServers] = useState(false)
	const [isSavingServer, setIsSavingServer] = useState(false)
	const [serverError, setServerError] = useState("")
	const [serverForm, setServerForm] = useState(() => createEmptyServerForm())
	const [headerRows, setHeaderRows] = useState([])
	const [deletingServerId, setDeletingServerId] = useState(null)
	const hasLoadedRef = useRef(false)

	const loadUserSettings = useCallback(async () => {
		const firstLoad = !hasLoadedRef.current
		if (firstLoad) setIsLoading(true)
		try {
			const settings = await getUserSettings()
			setInstructions(settings.custom_instructions || "")
			setOriginalInstructions(settings.custom_instructions || "")
			setMemoryCount(settings.memory_count || 0)
			hasLoadedRef.current = true
		} catch (error) {
			logger.error("Failed to load personalization settings", error)
		} finally {
			if (firstLoad) setIsLoading(false)
		}
	}, [])

	const loadMcpServers = useCallback(async () => {
		setIsLoadingServers(true)
		try {
			const response = await listMcpServers({ page: 1, pageSize: 50 })
			setMcpServers(response.items || [])
			setServerError("")
		} catch (error) {
			const detail = error?.data?.detail || error?.message || "Failed to load MCP servers"
			setServerError(detail)
		} finally {
			setIsLoadingServers(false)
		}
	}, [])

	const resetServerForm = useCallback(() => {
		setServerForm(createEmptyServerForm())
		setHeaderRows([])
		setServerError("")
	}, [])

	const addHeaderRow = useCallback(() => {
		setHeaderRows((prev) => [...prev, createHeaderRow()])
	}, [])

	const updateHeaderRow = useCallback((id, field, value) => {
		setHeaderRows((prev) => prev.map((row) => (row.id === id ? { ...row, [field]: value } : row)))
	}, [])

	const removeHeaderRow = useCallback((id) => {
		setHeaderRows((prev) => prev.filter((row) => row.id !== id))
	}, [])

	const handleAuthTypeChange = useCallback((authType) => {
		setServerForm((prev) => ({ ...prev, authType }))
	}, [])

	const handleCreateServer = async (event) => {
		event.preventDefault()
		setServerError("")

		const trimmedUrl = serverForm.url.trim()
		if (!trimmedUrl) {
			setServerError("Server URL is required")
			return
		}

		if (serverForm.authType === "bearer" && !serverForm.authToken.trim()) {
			setServerError("API token is required for bearer authentication")
			return
		}

		const headerEntries = headerRows
			.map((row) => ({ key: row.key.trim(), value: row.value.trim() }))
			.filter((row) => row.key && row.value)

		const payload = {
			url: trimmedUrl,
			auth_type: serverForm.authType,
			enabled: true,
		}

		if (serverForm.authType === "bearer") {
			payload.auth_token = serverForm.authToken.trim()
		}

		if (headerEntries.length > 0) {
			payload.headers = headerEntries.reduce((acc, row) => {
				acc[row.key] = row.value
				return acc
			}, {})
		}

		setIsSavingServer(true)
		try {
			const created = await createMcpServer(payload)
			setMcpServers((prev) => [created, ...prev])
			resetServerForm()
			setView(VIEW.MCP)
		} catch (error) {
			const detail = error?.data?.detail || error?.message || "Unable to add MCP server"
			setServerError(detail)
		} finally {
			setIsSavingServer(false)
		}
	}

	const handleDeleteServer = async (serverId) => {
		if (!window.confirm("Remove this MCP server?")) return
		setServerError("")
		setDeletingServerId(serverId)
		try {
			await deleteMcpServer(serverId)
			setMcpServers((prev) => prev.filter((server) => server.id !== serverId))
		} catch (error) {
			const detail = error?.data?.detail || error?.message || "Failed to remove MCP server"
			setServerError(detail)
		} finally {
			setDeletingServerId(null)
		}
	}

	useEffect(() => {
		if (open) {
			loadUserSettings()
			loadMcpServers()
		}
	}, [open, loadUserSettings, loadMcpServers])

	useEffect(() => {
		if (!open) {
			setView(VIEW.MAIN)
			resetServerForm()
		}
	}, [open, resetServerForm])

	const hasChanges = instructions !== originalInstructions

	const handleSave = async () => {
		setIsSaving(true)
		try {
			await updateCustomInstructions(instructions)
			setOriginalInstructions(instructions)
		} catch (error) {
			logger.error("Failed to update custom instructions", error)
		} finally {
			setIsSaving(false)
		}
	}

	const handleClearMemory = async () => {
		if (!window.confirm("Clear all memories? This cannot be undone.")) return
		setIsClearing(true)
		try {
			await clearUserMemory()
			setMemoryCount(0)
			setMemories([])
		} catch (error) {
			logger.error("Failed to clear memories", error)
		} finally {
			setIsClearing(false)
		}
	}

	const handleViewMemories = async () => {
		setView(VIEW.MEMORIES)
		if (memories.length === 0) {
			setIsLoadingMemories(true)
			try {
				const userMemories = await getUserMemories()
				setMemories(userMemories)
			} catch (error) {
				logger.error("Failed to load memories", error)
			} finally {
				setIsLoadingMemories(false)
			}
		}
	}

	const formatTimestamp = (timestamp) => {
		if (!timestamp) return ""
		try {
			const date = new Date(timestamp)
			const now = new Date()
			const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24))
			if (diffDays === 0) return "Today"
			if (diffDays === 1) return "Yesterday"
			if (diffDays < 7) return `${diffDays} days ago`
			return date.toLocaleDateString()
		} catch {
			return ""
		}
	}

	const handleDeleteMemory = async (memoryId) => {
		try {
			await deleteMemory(memoryId)
			setMemories((prev) => prev.filter((m) => m.id !== memoryId))
			setMemoryCount((prev) => Math.max(0, prev - 1))
		} catch (error) {
			logger.error("Failed to delete memory", error, { memoryId })
		}
	}

	const characterCount = instructions.length
	const maxCharacters = 1500

	// Render header based on current view
	const renderHeader = () => {
		const headers = {
			[VIEW.MAIN]: { title: "Personalization", subtitle: "Customize how AI responds to you", icon: Sparkles },
			[VIEW.MEMORIES]: {
				title: "Your Memories",
				subtitle: `${memoryCount} insights learned from interactions`,
				icon: Zap,
				back: VIEW.MAIN,
			},
			[VIEW.MCP]: {
				title: "Connected Tools",
				subtitle: "Extend AI with external services",
				icon: Server,
				back: VIEW.MAIN,
			},
			[VIEW.MCP_ADD]: { title: "Add Server", subtitle: "Connect an MCP server", icon: Plus, back: VIEW.MCP },
		}
		const h = headers[view]
		const IconComponent = h.icon

		return (
			<DialogHeader className="space-y-2">
				<div className="flex items-center gap-3">
					{h.back ? (
						<button
							type="button"
							onClick={() => {
								if (view === VIEW.MCP_ADD) resetServerForm()
								setView(h.back)
							}}
							className="p-2 -ml-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-all"
						>
							<ArrowLeft className="size-5 " />
						</button>
					) : (
						<div className="p-2.5 bg-linear-to-br from-primary/90 to-primary rounded-lg">
							<IconComponent className="size-5  text-white" />
						</div>
					)}
					<DialogTitle className="text-2xl">{h.title}</DialogTitle>
				</div>
				<DialogDescription>{h.subtitle}</DialogDescription>
			</DialogHeader>
		)
	}

	// Main view content
	const renderMainView = () => (
		<div className="space-y-5">
			{/* Custom Instructions Card */}
			<div className="space-y-3">
				<Label htmlFor="instructions" className="text-sm font-medium">
					Custom Instructions
				</Label>
				<div className="space-y-2">
					<textarea
						id="instructions"
						value={instructions}
						onChange={(e) => setInstructions(e.target.value)}
						placeholder="Tell the AI how you'd like it to respond. For example: 'I prefer concise explanations with practical examples' or 'I'm a visual learner who likes diagrams and step-by-step guides.'"
						className="w-full min-h-[120px] p-3 text-sm border border-border bg-card rounded-md resize-y focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring"
						maxLength={maxCharacters}
					/>

					<div className="flex justify-between items-center text-xs text-muted-foreground">
						<span>These instructions will be included in all AI interactions</span>
						<span className={characterCount > maxCharacters * 0.9 ? "text-destructive" : ""}>
							{characterCount}/{maxCharacters}
						</span>
					</div>
				</div>
			</div>

			{/* Quick Actions Grid */}
			<div className="grid grid-cols-2 gap-3">
				{/* Memory Card */}
				<button
					type="button"
					onClick={handleViewMemories}
					disabled={isLoadingMemories}
					className={cn(
						"group relative p-5 rounded-xl text-left transition-all duration-200",
						"bg-linear-to-br from-muted/50 to-muted/20",
						"border border-border/50 hover:border-border",
						"hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5"
					)}
				>
					<div className="flex items-center justify-between mb-3">
						<div className="p-2.5 rounded-xl bg-background border border-border/50 shadow-sm">
							<Zap className="size-4  text-primary" />
						</div>
						<ChevronRight className="size-4  text-muted-foreground/50 group-hover:text-muted-foreground transition-colors" />
					</div>
					<div className="text-3xl font-semibold tracking-tight text-foreground">{memoryCount}</div>
					<div className="text-sm text-muted-foreground mt-0.5">memories</div>
				</button>

				{/* MCP Card */}
				<button
					type="button"
					onClick={() => setView(VIEW.MCP)}
					disabled={isLoadingServers}
					className={cn(
						"group relative p-5 rounded-xl text-left transition-all duration-200",
						"bg-linear-to-br from-muted/50 to-muted/20",
						"border border-border/50 hover:border-border",
						"hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5"
					)}
				>
					<div className="flex items-center justify-between mb-3">
						<div className="p-2.5 rounded-xl bg-background border border-border/50 shadow-sm">
							<Server className="size-4  text-muted-foreground" />
						</div>
						<ChevronRight className="size-4  text-muted-foreground/50 group-hover:text-muted-foreground transition-colors" />
					</div>
					<div className="text-3xl font-semibold tracking-tight text-foreground">{mcpServers.length}</div>
					<div className="text-sm text-muted-foreground mt-0.5">tools connected</div>
				</button>
			</div>

			{/* Save Button */}
			<div className="flex items-center justify-end gap-3 pt-2">
				<Button variant="ghost" onClick={() => onOpenChange(false)} disabled={isSaving}>
					Cancel
				</Button>
				<Button onClick={handleSave} disabled={!hasChanges || isSaving} className="min-w-[120px]">
					{isSaving ? <Loader2 className="size-4  animate-spin" /> : "Save Changes"}
				</Button>
			</div>
		</div>
	)

	// Memories view content
	const renderMemoriesView = () => {
		let memoriesContent = null
		if (isLoadingMemories) {
			memoriesContent = (
				<div className="flex items-center justify-center py-16">
					<Loader2 className="size-5  animate-spin text-muted-foreground" />
				</div>
			)
		} else if (memories.length === 0) {
			memoriesContent = (
				<div className="py-16 text-center">
					<div className="inline-flex items-center justify-center size-14  rounded-2xl bg-muted/50 mb-4">
						<Zap className="size-6  text-muted-foreground/50" />
					</div>
					<p className="text-sm text-muted-foreground">No memories yet</p>
					<p className="text-xs text-muted-foreground/70 mt-1">Memories are created as you learn</p>
				</div>
			)
		} else {
			memoriesContent = (
				<div className="space-y-2">
					{memories.map((memory, index) => (
						<div
							key={memory.id || index}
							className={cn(
								"group relative p-4 rounded-xl transition-all duration-200",
								"bg-muted/30 hover:bg-muted/50",
								"border border-transparent hover:border-border/50"
							)}
						>
							<button
								type="button"
								onClick={() => handleDeleteMemory(memory.id)}
								className={cn(
									"absolute top-3 right-3 p-2 rounded-lg",
									"opacity-0 group-hover:opacity-100",
									"text-muted-foreground hover:text-destructive hover:bg-destructive/10",
									"transition-all duration-200"
								)}
							>
								<X className="size-3.5 " />
							</button>
							<p className="text-sm/relaxed text-foreground pr-10 ">{memory.content}</p>
							{formatTimestamp(memory.timestamp) && (
								<p className="text-xs text-muted-foreground/70 mt-2">{formatTimestamp(memory.timestamp)}</p>
							)}
						</div>
					))}

					{/* Clear all button */}
					{memories.length > 0 && (
						<div className="pt-4 flex justify-center">
							<Button
								variant="ghost"
								size="sm"
								onClick={handleClearMemory}
								disabled={isClearing}
								className="text-destructive hover:text-destructive hover:bg-destructive/10"
							>
								{isClearing ? <Loader2 className="size-4  animate-spin mr-2" /> : null}
								Clear All Memories
							</Button>
						</div>
					)}
				</div>
			)
		}

		return <div className="space-y-3">{memoriesContent}</div>
	}

	// MCP servers list view
	const renderMcpView = () => (
		<div className="space-y-3">
			{serverError && (
				<div className="mb-4 p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-sm text-destructive">
					{serverError}
				</div>
			)}

			{isLoadingServers ? (
				<div className="flex items-center justify-center py-16">
					<Loader2 className="size-5  animate-spin text-muted-foreground" />
				</div>
			) : (
				<div className="space-y-3">
					{mcpServers.map((server) => (
						<div
							key={server.id}
							className={cn(
								"group flex items-center gap-4 p-4 rounded-xl transition-all duration-200",
								"bg-muted/30 hover:bg-muted/50",
								"border border-transparent hover:border-border/50"
							)}
						>
							<div className="p-2.5 rounded-xl bg-background border border-border/50 shadow-sm">
								<Server className="size-4  text-muted-foreground" />
							</div>
							<div className="flex-1 min-w-0">
								<div className="flex items-center gap-2">
									<span className="text-sm font-medium text-foreground truncate">{server.name}</span>
									{server.enabled && (
										<span className="size-2  rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
									)}
								</div>
								<p className="text-xs text-muted-foreground truncate mt-0.5">{server.url}</p>
							</div>
							<button
								type="button"
								onClick={() => handleDeleteServer(server.id)}
								disabled={deletingServerId === server.id}
								className={cn(
									"p-2 rounded-lg opacity-0 group-hover:opacity-100",
									"text-muted-foreground hover:text-destructive hover:bg-destructive/10",
									"transition-all duration-200"
								)}
							>
								{deletingServerId === server.id ? (
									<Loader2 className="size-4  animate-spin" />
								) : (
									<Trash2 className="size-4 " />
								)}
							</button>
						</div>
					))}

					{/* Add server button */}
					<button
						type="button"
						onClick={() => setView(VIEW.MCP_ADD)}
						className={cn(
							"w-full flex items-center justify-center gap-2 p-4 rounded-xl",
							"border-2 border-dashed border-border/60 hover:border-primary/40",
							"text-muted-foreground hover:text-foreground",
							"transition-all duration-200 hover:bg-muted/30"
						)}
					>
						<Plus className="size-4 " />
						<span className="text-sm font-medium">Add MCP Server</span>
					</button>

					{mcpServers.length === 0 && (
						<p className="text-center text-xs text-muted-foreground/70 pt-2">
							Connect tools like Exa Search or Context7
						</p>
					)}
				</div>
			)}
		</div>
	)

	// Add MCP server form view
	const renderMcpAddView = () => (
		<div className="space-y-5">
			{serverError && (
				<div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-sm text-destructive">
					{serverError}
				</div>
			)}

			<div className="space-y-2">
				<Label htmlFor="server-url">Server URL</Label>
				<Input
					id="server-url"
					type="url"
					value={serverForm.url}
					onChange={(e) => setServerForm((prev) => ({ ...prev, url: e.target.value }))}
					placeholder="https://mcp.example.com"
					className="h-11"
				/>
				<p className="text-xs text-muted-foreground">Server name will be detected automatically</p>
			</div>

			<div className="space-y-3">
				<span className="block text-sm font-medium text-foreground">Authentication</span>
				<div className="flex gap-2">
					<button
						type="button"
						onClick={() => handleAuthTypeChange("none")}
						className={cn(
							"flex-1 rounded-xl border-2 px-4 py-2.5 text-sm font-medium transition-all duration-200",
							serverForm.authType === "none"
								? "border-primary bg-primary/5 text-primary"
								: "border-border/60 text-muted-foreground hover:border-border hover:text-foreground"
						)}
					>
						None
					</button>
					<button
						type="button"
						onClick={() => handleAuthTypeChange("bearer")}
						className={cn(
							"flex-1 rounded-xl border-2 px-4 py-2.5 text-sm font-medium transition-all duration-200",
							serverForm.authType === "bearer"
								? "border-primary bg-primary/5 text-primary"
								: "border-border/60 text-muted-foreground hover:border-border hover:text-foreground"
						)}
					>
						Bearer Token
					</button>
				</div>
				{serverForm.authType === "bearer" && (
					<Input
						type="password"
						value={serverForm.authToken}
						onChange={(e) => setServerForm((prev) => ({ ...prev, authToken: e.target.value }))}
						placeholder="Enter API token"
						className="h-11 mt-2"
					/>
				)}
			</div>

			{/* Headers */}
			{headerRows.length > 0 && (
				<div className="space-y-3">
					<span className="block text-sm font-medium text-foreground">Custom Headers</span>
					{headerRows.map((row) => (
						<div key={row.id} className="flex gap-2">
							<Input
								type="text"
								value={row.key}
								onChange={(e) => updateHeaderRow(row.id, "key", e.target.value)}
								placeholder="Header name"
								className="h-10"
							/>
							<Input
								type="text"
								value={row.value}
								onChange={(e) => updateHeaderRow(row.id, "value", e.target.value)}
								placeholder="Value"
								className="h-10"
							/>
							<button
								type="button"
								onClick={() => removeHeaderRow(row.id)}
								className="p-2 text-muted-foreground hover:text-destructive transition-colors"
							>
								<X className="size-4 " />
							</button>
						</div>
					))}
				</div>
			)}

			<button
				type="button"
				onClick={addHeaderRow}
				className="text-sm text-muted-foreground hover:text-foreground transition-colors"
			>
				+ Add custom header
			</button>

			<div className="flex items-center justify-end gap-3 pt-4">
				<Button
					variant="ghost"
					onClick={() => {
						resetServerForm()
						setView(VIEW.MCP)
					}}
					disabled={isSavingServer}
				>
					Cancel
				</Button>
				<Button
					onClick={handleCreateServer}
					disabled={isSavingServer || !serverForm.url.trim()}
					className="min-w-[100px]"
				>
					{isSavingServer ? <Loader2 className="size-4  animate-spin" /> : "Connect"}
				</Button>
			</div>
		</div>
	)

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-[520px] gap-5">
				{isLoading ? (
					<div className="flex items-center justify-center py-24">
						<Loader2 className="size-6  animate-spin text-muted-foreground" />
					</div>
				) : (
					<>
						{renderHeader()}
						<div className="max-h-[55vh] overflow-y-auto -mx-6 px-6">
							{view === VIEW.MAIN && renderMainView()}
							{view === VIEW.MEMORIES && renderMemoriesView()}
							{view === VIEW.MCP && renderMcpView()}
							{view === VIEW.MCP_ADD && renderMcpAddView()}
						</div>
					</>
				)}
			</DialogContent>
		</Dialog>
	)
}

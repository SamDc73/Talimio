import { Server, Settings2, Sparkles, User } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/Button"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import { Separator } from "@/components/Separator"
import { cn } from "@/lib/utils"

const VARIANTS = [
	{ id: "a", label: "A" },
	{ id: "b", label: "B" },
	{ id: "c", label: "C" },
	{ id: "d", label: "D" },
	{ id: "e", label: "E" },
]

const DEMO_EMAIL = "sam@talimio.ai"
const DEMO_USERNAME = "samdc"
const DEMO_MODELS = ["GPT-5.4", "Claude Sonnet 4.6", "Gemini 3.1 Pro"]
const DEMO_INSTRUCTIONS =
	"Teach me like a sharp, patient mentor. Start visual and concrete, then tighten into principles."
const DEMO_MEMORIES = [
	{ id: "memory-visuals", text: "Prefers diagrams and side-by-side explanations before abstract theory." },
	{ id: "memory-direct", text: "Wants a clear recommendation when there is an obvious best path." },
	{ id: "memory-night", text: "Usually studies late at night, so concise structure reduces fatigue." },
]
const DEMO_TOOLS = [
	{ id: "exa", name: "Exa Search", url: "https://mcp.exa.ai" },
	{ id: "context7", name: "Context7 Docs", url: "https://mcp.context7.dev" },
]

function removeMemoryById(memoryId) {
	return (current) => current.filter((item) => item.id !== memoryId)
}

function removeToolById(toolId) {
	return (current) => current.filter((item) => item.id !== toolId)
}

function AccountContent({ variantLabel }) {
	return (
		<div className="space-y-6">
			<div>
				<h2 className="text-lg font-semibold">Account</h2>
			</div>

			<div className="space-y-3">
				<div className="grid gap-1.5">
					<Label className="text-xs text-muted-foreground">Email</Label>
					<div className="text-sm">{DEMO_EMAIL}</div>
				</div>
				<div className="grid gap-1.5">
					<Label className="text-xs text-muted-foreground">Username</Label>
					<div className="text-sm">{DEMO_USERNAME}</div>
				</div>
			</div>

			<Separator />

			<div>
				<h3 className="text-sm font-medium">Change Password</h3>
			</div>
			<div className="grid gap-3">
				<div className="grid gap-1.5">
					<Label htmlFor={`pw-current-${variantLabel}`} className="text-xs">
						Current
					</Label>
					<Input id={`pw-current-${variantLabel}`} type="password" placeholder="Current password" className="h-9" />
				</div>
				<div className="grid gap-1.5">
					<Label htmlFor={`pw-new-${variantLabel}`} className="text-xs">
						New
					</Label>
					<Input id={`pw-new-${variantLabel}`} type="password" placeholder="New password" className="h-9" />
				</div>
				<div className="grid gap-1.5">
					<Label htmlFor={`pw-confirm-${variantLabel}`} className="text-xs">
						Confirm
					</Label>
					<Input id={`pw-confirm-${variantLabel}`} type="password" placeholder="Confirm new password" className="h-9" />
				</div>
			</div>
			<Button size="sm">Update Password</Button>

			<Separator />

			<div>
				<h3 className="text-sm font-medium text-destructive">Delete Account</h3>
			</div>
			<Button variant="destructive" size="sm">
				Delete Account
			</Button>
		</div>
	)
}

function PersonalizationContent() {
	const [selectedModel, setSelectedModel] = useState(DEMO_MODELS[0])
	const [instructions, setInstructions] = useState(DEMO_INSTRUCTIONS)
	const [memories, setMemories] = useState(DEMO_MEMORIES)
	const [view, setView] = useState("overview")

	if (view === "memories") {
		return (
			<div className="space-y-6">
				<div className="flex items-center justify-between gap-3">
					<Button variant="ghost" size="sm" onClick={() => setView("overview")}>
						Back
					</Button>
					<Button
						variant="ghost"
						size="sm"
						disabled={memories.length === 0}
						onClick={() => setMemories([])}
						className="text-destructive hover:text-destructive"
					>
						Clear All
					</Button>
				</div>

				<div>
					<h2 className="text-lg font-semibold">Memories</h2>
					<p className="mt-1 text-sm text-muted-foreground">{memories.length} saved</p>
				</div>

				{memories.length === 0 ? (
					<div className="rounded-lg border border-border bg-muted/30 px-3 py-6 text-sm text-muted-foreground">
						No memories saved.
					</div>
				) : (
					<div className="space-y-2">
						{memories.map((memory) => (
							<div
								key={memory.id}
								className="flex items-start justify-between gap-3 rounded-lg border border-border p-3 "
							>
								<p className="text-sm text-foreground">{memory.text}</p>
								<Button
									variant="ghost"
									size="sm"
									onClick={() => setMemories(removeMemoryById(memory.id))}
									className="shrink-0 text-destructive hover:text-destructive"
								>
									Delete
								</Button>
							</div>
						))}
					</div>
				)}
			</div>
		)
	}

	return (
		<div className="space-y-6">
			<div>
				<h2 className="text-lg font-semibold">Personalization</h2>
			</div>

			<div className="space-y-4">
				<h3 className="text-sm font-medium">Model</h3>
				<select
					value={selectedModel}
					onChange={(e) => setSelectedModel(e.target.value)}
					className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1"
				>
					{DEMO_MODELS.map((model) => (
						<option key={model} value={model}>
							{model}
						</option>
					))}
				</select>
			</div>

			<Separator />

			<div className="space-y-4">
				<h3 className="text-sm font-medium">Instructions</h3>
				<textarea
					value={instructions}
					onChange={(e) => setInstructions(e.target.value)}
					className="min-h-[100px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1"
				/>
				<div className="text-xs text-right text-muted-foreground">{instructions.length}/1500</div>
			</div>

			<Separator />

			<div className="space-y-3">
				<div className="flex items-center justify-between gap-3">
					<h3 className="text-sm font-medium">Memories</h3>
					<Button variant="outline" size="sm" onClick={() => setView("memories")}>
						Manage
					</Button>
				</div>
				<div className="rounded-lg border border-border bg-muted/30 p-3 ">
					<p className="text-sm font-medium text-foreground">{memories.length} saved</p>
					<p className="mt-1 text-sm text-muted-foreground">
						Delete individual memories or clear all from a dedicated view.
					</p>
				</div>
			</div>
		</div>
	)
}

function McpContent() {
	const [tools, setTools] = useState(DEMO_TOOLS)

	return (
		<div className="space-y-6">
			<div>
				<h2 className="text-lg font-semibold">MCP</h2>
			</div>

			<div className="space-y-2">
				{tools.map((tool) => (
					<div key={tool.id} className="flex items-center justify-between gap-3 rounded-lg border border-border p-3 ">
						<div>
							<p className="text-sm font-medium text-foreground">{tool.name}</p>
							<p className="mt-1 text-xs text-muted-foreground">{tool.url}</p>
						</div>
						<Button
							variant="ghost"
							size="sm"
							onClick={() => setTools(removeToolById(tool.id))}
							className="shrink-0 text-destructive hover:text-destructive"
						>
							Delete
						</Button>
					</div>
				))}
			</div>

			<Button variant="outline" size="sm" className="border-dashed">
				Add Server
			</Button>
		</div>
	)
}

function renderContent(tab, variantLabel) {
	if (tab === "account") {
		return <AccountContent variantLabel={variantLabel} />
	}

	if (tab === "personalization") {
		return <PersonalizationContent />
	}

	return <McpContent />
}

function WindowA() {
	const [tab, setTab] = useState("account")

	return (
		<div className="mx-auto w-full max-w-3xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
			<header className="flex items-center gap-4 border-b border-border px-6 py-4">
				<div className="flex items-center gap-3">
					<div className="rounded-lg bg-muted p-2">
						<Settings2 className="size-4" />
					</div>
					<h1 className="text-lg font-semibold">Settings</h1>
				</div>
			</header>
			<div className="flex">
				<nav className="w-52 space-y-1 border-r border-border p-3">
					<button
						type="button"
						onClick={() => setTab("account")}
						className={cn(
							"flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
							tab === "account"
								? "bg-primary/10 text-primary"
								: "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
						)}
					>
						<User className="size-4" />
						Account
					</button>
					<button
						type="button"
						onClick={() => setTab("personalization")}
						className={cn(
							"flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
							tab === "personalization"
								? "bg-primary/10 text-primary"
								: "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
						)}
					>
						<Sparkles className="size-4" />
						Personalization
					</button>
					<button
						type="button"
						onClick={() => setTab("mcp")}
						className={cn(
							"flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
							tab === "mcp"
								? "bg-primary/10 text-primary"
								: "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
						)}
					>
						<Server className="size-4" />
						MCP
					</button>
				</nav>
				<div className="flex-1 overflow-y-auto p-6">{renderContent(tab, "a")}</div>
			</div>
		</div>
	)
}

function WindowB() {
	const [tab, setTab] = useState("account")

	return (
		<div className="mx-auto w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
			<header className="border-b border-border px-6 py-4">
				<h1 className="text-lg font-semibold">Settings</h1>
				<div className="mt-3 flex gap-1">
					{["account", "personalization", "mcp"].map((item) => (
						<button
							key={item}
							type="button"
							onClick={() => setTab(item)}
							className={cn(
								"rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors",
								tab === item ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground"
							)}
						>
							{item}
						</button>
					))}
				</div>
			</header>
			<div className="overflow-y-auto p-6">{renderContent(tab, "b")}</div>
		</div>
	)
}

function WindowC() {
	const [tab, setTab] = useState("account")

	return (
		<div className="mx-auto w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
			<header className="border-b border-border px-6 py-4">
				<div className="flex items-center justify-between gap-3">
					<h1 className="text-lg font-semibold">Settings</h1>
					<div className="inline-flex rounded-lg border border-border p-0.5">
						{["account", "personalization", "mcp"].map((item) => (
							<button
								key={item}
								type="button"
								onClick={() => setTab(item)}
								className={cn(
									"rounded-md px-3 py-1 text-sm font-medium capitalize transition-colors",
									tab === item ? "bg-primary text-primary-foreground" : "text-muted-foreground"
								)}
							>
								{item}
							</button>
						))}
					</div>
				</div>
			</header>
			<div className="overflow-y-auto p-6">{renderContent(tab, "c")}</div>
		</div>
	)
}

function WindowD() {
	const [tab, setTab] = useState("account")

	return (
		<div className="mx-auto w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
			<div className="border-b border-border px-6 pt-5">
				<h1 className="text-lg font-semibold">Settings</h1>
				<div className="-mb-px mt-3 flex gap-6 border-b border-border">
					{["account", "personalization", "mcp"].map((item) => (
						<button
							key={item}
							type="button"
							onClick={() => setTab(item)}
							className={cn(
								"border-b-2 pb-2.5 text-sm font-medium capitalize transition-colors",
								tab === item
									? "border-primary text-foreground"
									: "border-transparent text-muted-foreground hover:text-foreground"
							)}
						>
							{item}
						</button>
					))}
				</div>
			</div>
			<div className="overflow-y-auto p-6">{renderContent(tab, "d")}</div>
		</div>
	)
}

function WindowE() {
	const [tab, setTab] = useState("account")

	return (
		<div className="mx-auto w-full max-w-3xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
			<header className="flex items-center gap-3 border-b border-border px-6 py-4">
				<Settings2 className="size-4 text-muted-foreground" />
				<h1 className="text-lg font-semibold">Settings</h1>
				<div className="ml-auto flex gap-1 rounded-lg bg-muted p-0.5">
					{["account", "personalization", "mcp"].map((item) => (
						<button
							key={item}
							type="button"
							onClick={() => setTab(item)}
							className={cn(
								"rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors",
								tab === item ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
							)}
						>
							{item}
						</button>
					))}
				</div>
			</header>
			<div className="overflow-y-auto p-6">{renderContent(tab, "e")}</div>
		</div>
	)
}

const WINDOWS = { a: WindowA, b: WindowB, c: WindowC, d: WindowD, e: WindowE }

export default function SettingsWindowDemoPage() {
	const [active, setActive] = useState("a")
	const Window = WINDOWS[active]

	return (
		<div className="min-h-screen bg-background text-foreground">
			<div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 md:px-6">
				<header className="rounded-2xl border border-border bg-card px-6 py-5 shadow-sm">
					<p className="text-sm font-medium text-primary">Local Demo</p>
					<h1 className="mt-1 text-2xl font-semibold tracking-tight">Settings Window Demo</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						One content split only: Account, Personalization, and MCP. Compare the chrome styles only.
					</p>
					<div className="mt-4 flex flex-wrap gap-3 text-sm">
						<Link className="text-primary underline underline-offset-4" to="/demos">
							Back to demos
						</Link>
						<Link className="text-primary underline underline-offset-4" to="/">
							Back home
						</Link>
					</div>
				</header>

				<section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
					<h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Chrome style</h2>
					<div className="mt-3 flex gap-2">
						{VARIANTS.map((variant) => (
							<button
								key={variant.id}
								type="button"
								onClick={() => setActive(variant.id)}
								className={cn(
									"rounded-lg border px-4 py-2 text-sm font-semibold transition-colors",
									active === variant.id
										? "border-primary bg-primary/10 text-primary"
										: "border-border text-muted-foreground hover:text-foreground"
								)}
							>
								{variant.label}
							</button>
						))}
					</div>
				</section>

				<section className="rounded-2xl border border-border bg-muted/30 p-6">
					<Window key={active} />
				</section>
			</div>
		</div>
	)
}

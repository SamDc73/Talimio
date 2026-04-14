import { ArrowLeft, Settings2, User, Zap } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import { AccountTab } from "./AccountTab"
import { ModelTab } from "./ModelTab"

const TABS = [
	{ id: "account", label: "Account", icon: User },
	{ id: "model", label: "Model", icon: Zap },
]

export function SettingsPage() {
	const [activeTab, setActiveTab] = useState("account")
	const navigate = useNavigate()

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay/60 p-4">
			<div className="w-full max-w-3xl bg-background rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
				<header className="flex items-center gap-4 px-6 py-4 border-b border-border">
					<button
						type="button"
						onClick={() => navigate(-1)}
						className="p-2 -ml-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
					>
						<ArrowLeft className="size-5" />
					</button>
					<div className="flex items-center gap-3">
						<div className="p-2 rounded-lg bg-muted">
							<Settings2 className="size-5" />
						</div>
						<h1 className="text-xl font-semibold">Settings</h1>
					</div>
				</header>

				<div className="flex flex-1 overflow-hidden">
					<nav className="w-48 border-r border-border p-3 space-y-1">
						{TABS.map((tab) => {
							const Icon = tab.icon
							return (
								<button
									key={tab.id}
									type="button"
									onClick={() => setActiveTab(tab.id)}
									className={cn(
										"w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
										activeTab === tab.id
											? "bg-primary/10 text-primary"
											: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
									)}
								>
									<Icon className="size-4" />
									{tab.label}
								</button>
							)
						})}
					</nav>

					<div className="flex-1 overflow-y-auto p-6">
						{activeTab === "account" && <AccountTab />}
						{activeTab === "model" && <ModelTab />}
					</div>
				</div>
			</div>
		</div>
	)
}

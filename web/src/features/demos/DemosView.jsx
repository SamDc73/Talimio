import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

const localDemosEnabled = import.meta.env.DEV

const LOCAL_DEMO_ROUTE_DEFINITIONS = [
	{
		id: "headers",
		path: "/headers",
		title: "Header playground",
		description: "Local-only header scratch page for comparing top-of-page treatments.",
		modulePathCandidates: [
			"/src/local-demos/HeaderPlayground.jsx",
			"/src/local-demos/HeaderPlaygroundPage.jsx",
			"/src/local-demos/HeadersDemoPage.jsx",
		],
	},
	{
		id: "lesson-visuals-demo",
		path: "/lesson-visuals-demo",
		title: "Lesson visual demo",
		description: "Local MDX scratch page comparing image, SVG, and spec-driven lesson visuals.",
		modulePathCandidates: ["/src/local-demos/LessonVisualsDemoPage.jsx"],
	},
	{
		id: "lesson-flow-greens",
		path: "/lesson-flow-greens",
		title: "Lesson flow greens",
		description: "Local palette study for lesson UI tone and readability.",
		modulePathCandidates: ["/src/local-demos/LessonFlowGreensDemoPage.jsx"],
	},
]

// biome-ignore lint/style/useComponentExportOnlyModules: route metadata stays colocated with the route component in this local-only module.
export const localDemoRoutes = LOCAL_DEMO_ROUTE_DEFINITIONS.map((route) => {
	return {
		...route,
		isAvailable: localDemosEnabled,
	}
})

const loadLocalDemoModule = async (modulePathCandidates) => {
	let lastError = null

	for (const modulePath of modulePathCandidates) {
		try {
			return await import(/* @vite-ignore */ modulePath)
		} catch (error) {
			lastError = error
		}
	}

	throw lastError ?? new Error("No local demo module could be loaded")
}

function LocalDemoState({ title, message }) {
	return (
		<div className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col justify-center gap-4 px-6 py-12">
			<p className="text-sm font-medium text-primary">Local Demo</p>
			<h1 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h1>
			<p className="max-w-2xl text-base/relaxed text-muted-foreground">{message}</p>
			<div className="flex flex-wrap gap-3 text-sm">
				<Link className="text-primary underline underline-offset-4" to="/demos">
					Browse local demo routes
				</Link>
				<Link className="text-primary underline underline-offset-4" to="/">
					Back home
				</Link>
			</div>
		</div>
	)
}

function LocalDemoLoading({ title }) {
	return <LocalDemoState title={title} message="Loading local demo..." />
}

function LocalDemoUnavailable({ title, description }) {
	return (
		<LocalDemoState
			title={title}
			message={
				localDemosEnabled
					? `${description} This route is optional and only works when the matching scratch file exists under src/local-demos in the current checkout.`
					: `${description} Local scratch routes are disabled outside the Vite dev server, so they never affect deploy builds.`
			}
		/>
	)
}

export function LocalDemoRoute({ demoId }) {
	const route = localDemoRoutes.find((item) => item.id === demoId)
	const [DemoComponent, setDemoComponent] = useState(null)
	const [loadError, setLoadError] = useState(null)
	const [isLoading, setIsLoading] = useState(localDemosEnabled)

	useEffect(() => {
		let isCancelled = false

		if (!route || !localDemosEnabled) {
			setDemoComponent(null)
			setLoadError(null)
			setIsLoading(false)
			return undefined
		}

		setIsLoading(true)
		setLoadError(null)
		setDemoComponent(null)

		const loadDemo = async () => {
			try {
				const module = await loadLocalDemoModule(route.modulePathCandidates)
				if (isCancelled) {
					return
				}

				const component = module?.default
				if (typeof component !== "function") {
					throw new TypeError(`Local demo ${route.title} is missing a default React component export.`)
				}

				setDemoComponent(() => component)
			} catch (error) {
				if (!isCancelled) {
					setLoadError(error)
				}
			} finally {
				if (!isCancelled) {
					setIsLoading(false)
				}
			}
		}

		loadDemo()

		return () => {
			isCancelled = true
		}
	}, [route])

	if (!route) {
		return <LocalDemoUnavailable title="Local demo" description="This local-only route is not registered." />
	}

	if (isLoading) {
		return <LocalDemoLoading title={route.title} />
	}

	if (!DemoComponent || loadError) {
		return <LocalDemoUnavailable title={route.title} description={route.description} />
	}

	return <DemoComponent />
}

export default function DemosView() {
	const availableRoutes = localDemoRoutes.filter((route) => route.isAvailable)
	const unavailableRoutes = localDemoRoutes.filter((route) => !route.isAvailable)

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-10">
			<header className="rounded-3xl border border-border bg-card p-6 shadow-sm">
				<p className="text-sm font-medium text-primary">Local Demos</p>
				<h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">Scratch routes for this checkout</h1>
				<p className="mt-3 max-w-3xl text-base/relaxed text-muted-foreground">
					These routes are optional. They load local files from <code>src/local-demos</code> only in the Vite dev
					server, so production builds never depend on scratch experiments.
				</p>
			</header>

			<section className="space-y-4">
				<h2 className="text-lg font-semibold text-foreground">Available now</h2>
				{availableRoutes.length > 0 ? (
					<div className="grid gap-4">
						{availableRoutes.map((route) => (
							<Link
								key={route.id}
								to={route.path}
								className="rounded-2xl border border-border bg-card px-5 py-4 shadow-sm transition-colors hover:bg-muted/30"
							>
								<p className="text-base font-semibold text-foreground">{route.title}</p>
								<p className="mt-1 text-sm text-muted-foreground">{route.description}</p>
								<p className="mt-3 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground/70">
									{route.path}
								</p>
							</Link>
						))}
					</div>
				) : (
					<div className="rounded-2xl border border-dashed border-border bg-card px-5 py-6 text-sm text-muted-foreground">
						No local demo files are present in this checkout.
					</div>
				)}
			</section>

			{unavailableRoutes.length > 0 ? (
				<section className="space-y-4">
					<h2 className="text-lg font-semibold text-foreground">Optional routes not present here</h2>
					<div className="grid gap-4">
						{unavailableRoutes.map((route) => (
							<div key={route.id} className="rounded-2xl border border-dashed border-border px-5 py-4 text-sm">
								<p className="font-semibold text-foreground">{route.title}</p>
								<p className="mt-1 text-muted-foreground">{route.description}</p>
								<p className="mt-3 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground/70">
									{route.path}
								</p>
							</div>
						))}
					</div>
				</section>
			) : null}
		</div>
	)
}

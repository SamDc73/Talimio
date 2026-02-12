function AuthPageShell({ title, description, icon = null, contentClassName = "px-8 pb-8", children }) {
	return (
		<div className="min-h-screen w-full flex items-center justify-center bg-linear-to-br from-primary/10 via-background to-primary/10 p-4">
			<div className="w-full max-w-md rounded-2xl bg-card shadow-2xl shadow-primary/30 border border-primary/20 overflow-hidden transform transition-all duration-500 hover:shadow-xl hover:shadow-primary/40">
				<div className="px-8 pt-8 pb-6 text-center">
					{icon && (
						<div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
							{icon}
						</div>
					)}
					<h1 className="text-2xl font-bold text-foreground mb-2">{title}</h1>
					<p className="text-muted-foreground text-sm">{description}</p>
				</div>

				<div className={contentClassName}>{children}</div>
			</div>
		</div>
	)
}

export default AuthPageShell

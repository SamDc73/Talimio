// Renders a vision-verified lesson figure embedded from its original source URL.
// Attribution is legally required for CC-licensed images, so it always renders.
export function Figure({ src, alt, caption, attribution, license, sourcePage }) {
	if (typeof src !== "string" || !src.trim()) {
		return null
	}

	const altText = (typeof alt === "string" && alt.trim()) || (typeof caption === "string" && caption.trim()) || ""

	return (
		<figure className="my-6 flex flex-col items-center">
			<img
				src={src}
				alt={altText}
				loading="lazy"
				className="max-h-112 w-auto max-w-full rounded-lg border border-border bg-card"
			/>
			{caption ? <figcaption className="mt-3 text-sm text-muted-foreground text-center">{caption}</figcaption> : null}
			{attribution || license ? (
				<div className="mt-1 text-xs text-muted-foreground/70 text-center">
					{sourcePage ? (
						<a href={sourcePage} target="_blank" rel="noreferrer" className="hover:text-muted-foreground underline">
							{attribution || "Source"}
						</a>
					) : (
						attribution
					)}
					{attribution && license ? " · " : null}
					{license}
				</div>
			) : null}
		</figure>
	)
}

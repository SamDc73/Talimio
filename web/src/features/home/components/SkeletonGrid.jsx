export default function SkeletonGrid({ count = 6 }) {
	return (
		<>
			{Array.from({ length: count }).map(() => (
				<div key={crypto.randomUUID()} className="animate-pulse">
					<div className="bg-muted/50 dark:bg-background/70 rounded-xl h-64" />
				</div>
			))}
		</>
	)
}

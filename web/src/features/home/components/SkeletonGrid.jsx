export default function SkeletonGrid({ count = 6 }) {
	return (
		<>
			{Array.from({ length: count }).map(() => (
				<div key={crypto.randomUUID()} className="animate-pulse">
					<div className="bg-gray-200 dark:bg-gray-700 rounded-xl h-64" />
				</div>
			))}
		</>
	)
}

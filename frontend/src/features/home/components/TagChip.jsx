export function TagChip({ tag, colorClass }) {
	return (
		<span
			className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}
		>
			{tag}
		</span>
	);
}

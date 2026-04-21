export function NestedComponentFixture({ label }) {
	function Inner() {
		return <span>{label}</span>
	}

	return <Inner />
}

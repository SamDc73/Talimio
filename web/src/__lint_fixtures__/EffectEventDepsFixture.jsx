import { useEffect, useEffectEvent } from "react"

export function EffectEventDepsFixture() {
	const onSomething = useEffectEvent(() => {})

	useEffect(() => {
		onSomething()
	}, [onSomething])

	return null
}

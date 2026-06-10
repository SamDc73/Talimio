import { useEffect, useEffectEvent } from "react"
import { noop } from "@/lib/utils"

export function EffectEventDepsFixture() {
	const onSomething = useEffectEvent(noop)

	useEffect(() => {
		onSomething()
	}, [onSomething])

	return null
}

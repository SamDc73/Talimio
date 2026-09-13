import { useMemo } from "react"
import { JXGBoard } from "@/components/JXGBoard"

/**
 * Draws a stored question figure: one `board.create(type, parents, attributes)`
 * call per element, so diagrams travel as data instead of screenshots.
 */
export function JXGFigure({ figure, className }) {
	const setup = useMemo(() => {
		if (!figure || !Array.isArray(figure.elements)) {
			return null
		}
		return ({ board }) => {
			for (const element of figure.elements) {
				board.create(element.type, element.parents, element.attributes ?? {})
			}
		}
	}, [figure])

	if (!setup) {
		return null
	}

	return (
		<JXGBoard
			boundingBox={figure.boundingBox}
			axis={figure.axis === true}
			grid={figure.grid === true}
			keepAspectRatio={figure.keepAspectRatio !== false}
			setup={setup}
			className={className}
		/>
	)
}

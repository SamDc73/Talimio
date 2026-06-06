import { AnimatePresence, motion } from "framer-motion"
import { useId } from "react"

// Mercury Forge — the loading graphic is the demo's liquid-mercury cluster: a few
// accent droplets drift on their own gentle timelines and, under an SVG goo filter
// (blur + alpha threshold makes overlapping blobs read as one continuous surface),
// meet near the center to fuse into a single bead, then part again. The witty
// message sits below as crisp, fully legible type — the metal and the words move
// together as one piece, but the goo never touches the letters (no blending).

const ACCENT = "var(--color-course)"
const LOOP = Number.POSITIVE_INFINITY

// Droplet motion copied verbatim from the demo scene: each blob eases from -> to ->
// from on its own duration, so they converge and separate organically (never a rigid
// beat). x/y are pixel offsets from the cluster center.
const DROPLETS = [
	{ id: "d0", size: 16, from: { x: -48, y: 6 }, to: { x: -16, y: -6 }, duration: 3.2 },
	{ id: "d1", size: 13, from: { x: 46, y: -8 }, to: { x: 14, y: 7 }, duration: 4.0 },
	{ id: "d2", size: 11, from: { x: 4, y: 15 }, to: { x: -6, y: -5 }, duration: 3.6 },
]

export function MercuryForgeLoader({ message }) {
	// useId can contain ":" which is invalid inside a CSS url(#...) reference.
	const gooId = `goo-${useId().replace(/:/g, "")}`

	return (
		<div className="flex flex-col items-center justify-center gap-6" role="status" aria-live="polite">
			<span className="sr-only">{message}</span>

			<svg width="0" height="0" className="absolute" aria-hidden="true">
				<title>liquid filter</title>
				<defs>
					<filter id={gooId} x="-50%" y="-80%" width="200%" height="260%">
						<feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
						<feColorMatrix in="blur" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 15 -5" />
					</filter>
				</defs>
			</svg>

			<div className="relative h-14 w-32" aria-hidden="true" style={{ filter: `url(#${gooId})` }}>
				{DROPLETS.map((drop) => (
					<motion.span
						key={drop.id}
						className="absolute rounded-full"
						style={{
							width: drop.size,
							height: drop.size,
							left: "50%",
							top: "50%",
							marginLeft: -drop.size / 2,
							marginTop: -drop.size / 2,
							background: ACCENT,
						}}
						initial={{ x: drop.from.x, y: drop.from.y }}
						animate={{ x: [drop.from.x, drop.to.x, drop.from.x], y: [drop.from.y, drop.to.y, drop.from.y] }}
						transition={{ duration: drop.duration, ease: "easeInOut", repeat: LOOP }}
					/>
				))}
			</div>

			<AnimatePresence mode="wait">
				<motion.p
					key={message}
					className="max-w-[28rem] text-center font-semibold text-[1.25rem] leading-snug text-(--color-course)"
					initial={{ opacity: 0, y: 6 }}
					animate={{ opacity: 1, y: 0 }}
					exit={{ opacity: 0, y: -6 }}
					transition={{ duration: 0.45, ease: "easeOut" }}
				>
					{message}
				</motion.p>
			</AnimatePresence>
		</div>
	)
}

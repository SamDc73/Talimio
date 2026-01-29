import { Annotation, Compartment, EditorState } from "@codemirror/state"
import { EditorView } from "@codemirror/view"
import { useEffect, useLayoutEffect, useRef } from "react"

const EXTERNAL_CHANGE = Annotation.define()

export default function CodeMirrorEditor({ value = "", onChange, extensions = [], className, style, ...props }) {
	const containerRef = useRef(null)
	const viewRef = useRef(null)
	const onChangeRef = useRef(onChange)
	const extensionsCompartmentRef = useRef(new Compartment())

	onChangeRef.current = onChange

	useLayoutEffect(() => {
		if (!containerRef.current) {
			return undefined
		}

		const updateListener = EditorView.updateListener.of((update) => {
			if (!update.docChanged) {
				return
			}

			if (update.transactions.some((tr) => tr.annotation(EXTERNAL_CHANGE))) {
				return
			}

			const nextValue = update.state.doc.toString()
			if (typeof onChangeRef.current === "function") {
				onChangeRef.current(nextValue, update)
			}
		})

		const state = EditorState.create({
			doc: typeof value === "string" ? value : String(value ?? ""),
			extensions: [updateListener, extensionsCompartmentRef.current.of(extensions)],
		})

		const view = new EditorView({
			state,
			parent: containerRef.current,
		})

		viewRef.current = view

		return () => {
			viewRef.current = null
			view.destroy()
		}
	}, [extensions, value])

	useEffect(() => {
		const view = viewRef.current
		if (!view) {
			return
		}

		view.dispatch({
			effects: extensionsCompartmentRef.current.reconfigure(extensions),
		})
	}, [extensions])

	useEffect(() => {
		const view = viewRef.current
		if (!view) {
			return
		}

		const nextValue = typeof value === "string" ? value : String(value ?? "")
		const currentValue = view.state.doc.toString()
		if (nextValue === currentValue) {
			return
		}

		view.dispatch({
			changes: { from: 0, to: currentValue.length, insert: nextValue },
			annotations: EXTERNAL_CHANGE.of(true),
		})
	}, [value])

	return <div ref={containerRef} className={className} style={style} {...props} />
}

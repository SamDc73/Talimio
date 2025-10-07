import { EditorView } from "@codemirror/view"
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language"
import { tags as t } from "@lezer/highlight"

function wrapHexPalette(palette) {
	const wrapped = {}
	for (const [key, hex] of Object.entries(palette)) {
		wrapped[key] = { hex }
	}
	return wrapped
}

const flavors = {
	latte: {
		dark: false,
		colors: wrapHexPalette({
			rosewater: "#dc8a78",
			flamingo: "#dd7878",
			pink: "#ea76cb",
			mauve: "#8839ef",
			red: "#d20f39",
			maroon: "#e64553",
			peach: "#fe640b",
			yellow: "#df8e1d",
			green: "#40a02b",
			teal: "#179299",
			sky: "#04a5e5",
			sapphire: "#209fb5",
			blue: "#1e66f5",
			lavender: "#7287fd",
			text: "#4c4f69",
			subtext1: "#5c5f77",
			subtext0: "#6c6f85",
			overlay2: "#7c7f93",
			overlay1: "#8c8fa1",
			overlay0: "#9ca0b0",
			surface2: "#acb0be",
			surface1: "#bcc0cc",
			surface0: "#ccd0da",
			base: "#eff1f5",
			mantle: "#e6e9ef",
			crust: "#dce0e8",
		}),
	},
	frappe: {
		dark: true,
		colors: wrapHexPalette({
			rosewater: "#f2d5cf",
			flamingo: "#eebebe",
			pink: "#f4b8e4",
			mauve: "#ca9ee6",
			red: "#e78284",
			maroon: "#ea999c",
			peach: "#ef9f76",
			yellow: "#e5c890",
			green: "#a6d189",
			teal: "#81c8be",
			sky: "#99d1db",
			sapphire: "#85c1dc",
			blue: "#8caaee",
			lavender: "#babbf1",
			text: "#c6d0f5",
			subtext1: "#b5bfe2",
			subtext0: "#a5adce",
			overlay2: "#949cbb",
			overlay1: "#838ba7",
			overlay0: "#737994",
			surface2: "#626880",
			surface1: "#51576d",
			surface0: "#414559",
			base: "#303446",
			mantle: "#292c3c",
			crust: "#232634",
		}),
	},
	macchiato: {
		dark: true,
		colors: wrapHexPalette({
			rosewater: "#f4dbd6",
			flamingo: "#f0c6c6",
			pink: "#f5bde6",
			mauve: "#c6a0f6",
			red: "#ed8796",
			maroon: "#ee99a0",
			peach: "#f5a97f",
			yellow: "#eed49f",
			green: "#a6da95",
			teal: "#8bd5ca",
			sky: "#91d7e3",
			sapphire: "#7dc4e4",
			blue: "#8aadf4",
			lavender: "#b7bdf8",
			text: "#cad3f5",
			subtext1: "#b8c0e0",
			subtext0: "#a5adcb",
			overlay2: "#939ab7",
			overlay1: "#8087a2",
			overlay0: "#6e738d",
			surface2: "#5b6078",
			surface1: "#494d64",
			surface0: "#363a4f",
			base: "#24273a",
			mantle: "#1e2030",
			crust: "#181926",
		}),
	},
	mocha: {
		dark: true,
		colors: wrapHexPalette({
			rosewater: "#f5e0dc",
			flamingo: "#f2cdcd",
			pink: "#f5c2e7",
			mauve: "#cba6f7",
			red: "#f38ba8",
			maroon: "#eba0ac",
			peach: "#fab387",
			yellow: "#f9e2af",
			green: "#a6e3a1",
			teal: "#94e2d5",
			sky: "#89dceb",
			sapphire: "#74c7ec",
			blue: "#89b4fa",
			lavender: "#b4befe",
			text: "#cdd6f4",
			subtext1: "#bac2de",
			subtext0: "#a6adc8",
			overlay2: "#9399b2",
			overlay1: "#7f849c",
			overlay0: "#6c7086",
			surface2: "#585b70",
			surface1: "#45475a",
			surface0: "#313244",
			base: "#1e1e2e",
			mantle: "#181825",
			crust: "#11111b",
		}),
	},
}

function createCatppuccinTheme(flavor) {
	const colors = flavor.colors
	const isDark = flavor.dark

	const theme = EditorView.theme(
		{
			"&": {
				color: colors.text.hex,
				backgroundColor: colors.base.hex,
				outline: "none",
			},
			"&.cm-focused": {
				outline: `2px solid ${colors.surface1.hex}`,
				outlineOffset: "0px",
				boxShadow: `0 0 0 4px ${colors.surface0.hex}66`,
				transition: "box-shadow 150ms ease, outline-color 150ms ease",
			},
			".cm-content": {
				caretColor: colors.rosewater.hex,
			},
			".cm-cursor, .cm-dropCursor": {
				borderLeftColor: colors.rosewater.hex,
			},
			"&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
				{
					backgroundColor: colors.surface2.hex,
				},
			".cm-panels": {
				backgroundColor: colors.mantle.hex,
				color: colors.text.hex,
			},
			".cm-panels.cm-panels-top": { borderBottom: "2px solid black" },
			".cm-panels.cm-panels-bottom": { borderTop: "2px solid black" },
			".cm-searchMatch": {
				backgroundColor: `${colors.blue.hex}59`,
				outline: `1px solid ${colors.blue.hex}`,
			},
			".cm-searchMatch.cm-searchMatch-selected": {
				backgroundColor: `${colors.blue.hex}2f`,
			},
			".cm-activeLine": { backgroundColor: "transparent" },
			".cm-activeLineGutter": { backgroundColor: "transparent" },
			".cm-selectionMatch": {
				backgroundColor: `${colors.surface2.hex}4d`,
			},
			"&.cm-focused .cm-matchingBracket, &.cm-focused .cm-nonmatchingBracket": {
				backgroundColor: `${colors.surface2.hex}47`,
				color: colors.text.hex,
			},
			".cm-gutters": {
				backgroundColor: colors.base.hex,
				color: colors.subtext0.hex,
				border: "none",
			},
			".cm-foldPlaceholder": {
				backgroundColor: "transparent",
				border: "none",
				color: colors.overlay0.hex,
			},
			".cm-tooltip": {
				border: "none",
				backgroundColor: colors.surface0.hex,
			},
			".cm-tooltip .cm-tooltip-arrow:before": {
				borderTopColor: "transparent",
				borderBottomColor: "transparent",
			},
			".cm-tooltip .cm-tooltip-arrow:after": {
				borderTopColor: colors.surface0.hex,
				borderBottomColor: colors.surface0.hex,
			},
			".cm-tooltip-autocomplete": {
				"& > ul > li[aria-selected]": {
					backgroundColor: colors.surface1.hex,
					color: colors.text.hex,
				},
			},
		},
		{ dark: isDark }
	)

	const highlightStyle = HighlightStyle.define([
		{ tag: t.keyword, color: colors.mauve.hex },
		{
			tag: [t.name, t.definition(t.name), t.deleted, t.character, t.macroName],
			color: colors.text.hex,
		},
		{
			tag: [t.function(t.variableName), t.function(t.propertyName), t.propertyName, t.labelName],
			color: colors.blue.hex,
		},
		{
			tag: [t.color, t.constant(t.name), t.standard(t.name)],
			color: colors.peach.hex,
		},
		{ tag: [t.self, t.atom], color: colors.red.hex },
		{
			tag: [t.typeName, t.className, t.changed, t.annotation, t.namespace],
			color: colors.yellow.hex,
		},
		{ tag: [t.operator], color: colors.sky.hex },
		{ tag: [t.url, t.link], color: colors.teal.hex },
		{ tag: [t.escape, t.regexp], color: colors.pink.hex },
		{
			tag: [t.meta, t.punctuation, t.separator, t.comment],
			color: colors.overlay2.hex,
		},
		{ tag: t.strong, fontWeight: "bold" },
		{ tag: t.emphasis, fontStyle: "italic" },
		{ tag: t.strikethrough, textDecoration: "line-through" },
		{ tag: t.link, color: colors.blue.hex, textDecoration: "underline" },
		{ tag: t.heading, fontWeight: "bold", color: colors.blue.hex },
		{
			tag: [t.special(t.variableName)],
			color: colors.lavender.hex,
		},
		{ tag: [t.bool, t.number], color: colors.peach.hex },
		{
			tag: [t.processingInstruction, t.string, t.inserted],
			color: colors.green.hex,
		},
		{ tag: t.invalid, color: colors.red.hex },
	])

	return [theme, syntaxHighlighting(highlightStyle)]
}

export const catppuccinLatte = createCatppuccinTheme(flavors.latte)
export const catppuccinFrappe = createCatppuccinTheme(flavors.frappe)
export const catppuccinMacchiato = createCatppuccinTheme(flavors.macchiato)
export const catppuccinMocha = createCatppuccinTheme(flavors.mocha)
export const catppuccinLatteColors = flavors.latte.colors

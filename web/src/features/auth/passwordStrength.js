import { zxcvbn, zxcvbnOptions } from "@zxcvbn-ts/core"
import { adjacencyGraphs, dictionary as commonDictionary } from "@zxcvbn-ts/language-common"
import { dictionary as enDictionary, translations as enTranslations } from "@zxcvbn-ts/language-en"

export const PASSWORD_SCORE_LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"]
export const PASSWORD_SCORE_STYLES = [
	"bg-destructive/40",
	"bg-destructive/55",
	"bg-amber-500/60",
	"bg-primary/70",
	"bg-primary",
]

zxcvbnOptions.setOptions({
	translations: enTranslations,
	graphs: adjacencyGraphs,
	dictionary: {
		...commonDictionary,
		...enDictionary,
	},
})

export const getPasswordStrength = (password, userInputs = []) => {
	if (!password) return null

	const cleanedInputs = userInputs.filter((value) => typeof value === "string" && value.trim().length > 0)
	const result = zxcvbn(password, cleanedInputs)
	const warning = result.feedback?.warning?.trim() || ""
	const suggestion = result.feedback?.suggestions?.[0] || ""
	const feedback = warning || suggestion || "Password strength looks good."

	return {
		score: result.score,
		label: PASSWORD_SCORE_LABELS[result.score],
		feedback,
	}
}

import { PASSWORD_SCORE_STYLES } from "@/features/auth/passwordStrength"

function PasswordStrengthMeter({ passwordStrength, meterIdPrefix = "password-strength" }) {
	if (!passwordStrength) {
		return null
	}

	return (
		<div className="rounded-xl border border-border bg-muted/20 px-3 py-2">
			<div className="mb-2 flex items-center justify-between text-xs">
				<span className="text-muted-foreground">Strength</span>
				<span className="font-medium text-foreground">{passwordStrength.label}</span>
			</div>
			<div className="mb-2 grid grid-cols-5 gap-1">
				{[0, 1, 2, 3, 4].map((step) => {
					const isFilled = step <= passwordStrength.score
					const baseClass = "h-1.5 rounded-full transition-colors"
					const filledClass = PASSWORD_SCORE_STYLES[passwordStrength.score]
					const emptyClass = "bg-muted"
					return (
						<div key={`${meterIdPrefix}-${step}`} className={`${baseClass} ${isFilled ? filledClass : emptyClass}`} />
					)
				})}
			</div>
			<p className="text-xs text-muted-foreground">{passwordStrength.feedback}</p>
		</div>
	)
}

export default PasswordStrengthMeter

const UPPERCASE_PATTERN = /[A-Z]/
const LOWERCASE_PATTERN = /[a-z]/
const DIGIT_PATTERN = /\d/
const SYMBOL_PATTERN = /[^A-Za-z0-9]/

const toBoolean = (value) => value === true

const toPositiveIntegerOrNull = (value) => {
	if (!Number.isInteger(value) || value <= 0) {
		return null
	}
	return value
}

export const normalizePasswordPolicy = (passwordPolicy) => {
	if (!passwordPolicy || typeof passwordPolicy !== "object") {
		return null
	}

	return {
		minLength: toPositiveIntegerOrNull(passwordPolicy.minLength),
		requireUppercase: toBoolean(passwordPolicy.requireUppercase),
		requireLowercase: toBoolean(passwordPolicy.requireLowercase),
		requireDigit: toBoolean(passwordPolicy.requireDigit),
		requireSymbol: toBoolean(passwordPolicy.requireSymbol),
		disallowWhitespace: toBoolean(passwordPolicy.disallowWhitespace),
	}
}

export const getPasswordPolicyValidationMessage = (password, passwordPolicy) => {
	if (!passwordPolicy) {
		return null
	}

	if (passwordPolicy.minLength && password.length < passwordPolicy.minLength) {
		return `Password must be at least ${passwordPolicy.minLength} characters`
	}
	if (passwordPolicy.requireUppercase && !UPPERCASE_PATTERN.test(password)) {
		return "Password must include an uppercase letter"
	}
	if (passwordPolicy.requireLowercase && !LOWERCASE_PATTERN.test(password)) {
		return "Password must include a lowercase letter"
	}
	if (passwordPolicy.requireDigit && !DIGIT_PATTERN.test(password)) {
		return "Password must include a number"
	}
	if (passwordPolicy.requireSymbol && !SYMBOL_PATTERN.test(password)) {
		return "Password must include a special character"
	}
	if (passwordPolicy.disallowWhitespace && /\s/.test(password)) {
		return "Password must not include whitespace"
	}

	return null
}

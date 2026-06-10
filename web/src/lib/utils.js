import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
	return twMerge(clsx(inputs))
}

/** Intentional no-op for optional callback defaults. */
export const noop = () => undefined

/** Intentional async no-op for optional async callback defaults. */
export const asyncNoop = async () => undefined

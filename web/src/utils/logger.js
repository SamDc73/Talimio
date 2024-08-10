const LOG_LEVELS = {
	DEBUG: 0,
	INFO: 1,
	WARN: 2,
	ERROR: 3,
}

const isDevelopment = import.meta.env.DEV
const currentLogLevel = isDevelopment ? LOG_LEVELS.DEBUG : LOG_LEVELS.WARN

const logger = {
	debug: (..._args) => {
		if (currentLogLevel <= LOG_LEVELS.DEBUG) {
		}
	},

	info: (..._args) => {
		if (currentLogLevel <= LOG_LEVELS.INFO) {
		}
	},

	warn: (..._args) => {
		if (currentLogLevel <= LOG_LEVELS.WARN) {
		}
	},

	error: (..._args) => {
		if (currentLogLevel <= LOG_LEVELS.ERROR) {
		}
	},

	group: (_label) => {
		if (isDevelopment) {
		}
	},

	groupEnd: () => {
		if (isDevelopment) {
		}
	},
}

export default logger

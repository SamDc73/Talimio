const LOG_LEVELS = {
	DEBUG: 0,
	INFO: 1,
	WARN: 2,
	ERROR: 3,
};

const isDevelopment = import.meta.env.DEV;
const currentLogLevel = isDevelopment ? LOG_LEVELS.DEBUG : LOG_LEVELS.WARN;

const logger = {
	debug: (...args) => {
		if (currentLogLevel <= LOG_LEVELS.DEBUG) {
			console.log("[DEBUG]", ...args);
		}
	},

	info: (...args) => {
		if (currentLogLevel <= LOG_LEVELS.INFO) {
			console.info("[INFO]", ...args);
		}
	},

	warn: (...args) => {
		if (currentLogLevel <= LOG_LEVELS.WARN) {
			console.warn("[WARN]", ...args);
		}
	},

	error: (...args) => {
		if (currentLogLevel <= LOG_LEVELS.ERROR) {
			console.error("[ERROR]", ...args);
		}
	},

	group: (label) => {
		if (isDevelopment) {
			console.group(label);
		}
	},

	groupEnd: () => {
		if (isDevelopment) {
			console.groupEnd();
		}
	},
};

export default logger;

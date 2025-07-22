// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
	darkMode: ["class"],
	content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
	theme: {
		container: {
			center: "true",
			padding: "2rem",
			screens: {
				"2xl": "1400px",
			},
		},
		extend: {
			colors: {
				border: "hsl(var(--border))",
				input: "hsl(var(--input))",
				ring: "hsl(var(--ring))",
				background: "hsl(var(--background))",
				foreground: "hsl(var(--foreground))",
				primary: {
					DEFAULT: "hsl(var(--primary))",
					foreground: "hsl(var(--primary-foreground))",
				},
				secondary: {
					DEFAULT: "hsl(var(--secondary))",
					foreground: "hsl(var(--secondary-foreground))",
				},
				destructive: {
					DEFAULT: "hsl(var(--destructive))",
					foreground: "hsl(var(--destructive-foreground))",
				},
				muted: {
					DEFAULT: "hsl(var(--muted))",
					foreground: "hsl(var(--muted-foreground))",
				},
				accent: {
					DEFAULT: "hsl(var(--accent))",
					foreground: "hsl(var(--accent-foreground))",
				},
				popover: {
					DEFAULT: "hsl(var(--popover))",
					foreground: "hsl(var(--popover-foreground))",
				},
				card: {
					DEFAULT: "hsl(var(--card))",
					foreground: "hsl(var(--card-foreground))",
				},
				chart: {
					1: "hsl(var(--chart-1))",
					2: "hsl(var(--chart-2))",
					3: "hsl(var(--chart-3))",
					4: "hsl(var(--chart-4))",
					5: "hsl(var(--chart-5))",
				},
				// Content Type Colors
				course: {
					DEFAULT: "hsl(var(--course-bg))",
					text: "hsl(var(--course-text))",
					accent: "hsl(var(--course-accent))",
				},
				book: {
					DEFAULT: "hsl(var(--book-bg))",
					text: "hsl(var(--book-text))",
					accent: "hsl(var(--book-accent))",
				},
				video: {
					DEFAULT: "hsl(var(--video-bg))",
					text: "hsl(var(--video-text))",
					accent: "hsl(var(--video-accent))",
				},
				flashcard: {
					DEFAULT: "hsl(var(--flashcard-bg))",
					text: "hsl(var(--flashcard-text))",
					accent: "hsl(var(--flashcard-accent))",
				},
				// Status Colors
				overdue: {
					DEFAULT: "hsl(var(--overdue-bg))",
					text: "hsl(var(--overdue-text))",
				},
				"due-today": {
					DEFAULT: "hsl(var(--due-today-bg))",
					text: "hsl(var(--due-today-text))",
				},
				upcoming: {
					DEFAULT: "hsl(var(--upcoming-bg))",
					text: "hsl(var(--upcoming-text))",
				},
				completed: {
					DEFAULT: "hsl(var(--completed-bg))",
					text: "hsl(var(--completed-text))",
				},
				paused: {
					DEFAULT: "hsl(var(--paused-bg))",
					text: "hsl(var(--paused-text))",
				},
			},
			borderRadius: {
				lg: "var(--radius)",
				md: "calc(var(--radius) - 2px)",
				sm: "calc(var(--radius) - 4px)",
			},
			fontFamily: {
				sans: ["var(--font-sans)"],
				display: ["var(--font-display)"],
			},
			keyframes: {
				"accordion-down": {
					from: {
						height: "0",
					},
					to: {
						height: "var(--radix-accordion-content-height)",
					},
				},
				"accordion-up": {
					from: {
						height: "var(--radix-accordion-content-height)",
					},
					to: {
						height: "0",
					},
				},
			},
			animation: {
				"accordion-down": "accordion-down 0.2s ease-out",
				"accordion-up": "accordion-up 0.2s ease-out",
			},
		},
	},
	plugins: [require("tailwindcss-animate")],
};

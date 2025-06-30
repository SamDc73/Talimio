import { Highlighter, Sparkles } from "lucide-react";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useRef,
	useState,
} from "react";

// Context for global tooltip
const TextSelectionContext = createContext(null);

export const useTextSelection = () => {
	const context = useContext(TextSelectionContext);
	if (!context) {
		throw new Error(
			"useTextSelection must be used within TextSelectionProvider",
		);
	}
	return context;
};

export const TextSelectionProvider = ({ children }) => {
	const [isOpen, setIsOpen] = useState(false);
	const [selectedText, setSelectedText] = useState("");
	const [handlers, setHandlers] = useState({
		onHighlight: null,
		onAskAI: null,
	});
	const selectionTimeoutRef = useRef(null);
	const tooltipRef = useRef(null);
	const [tooltipX, setTooltipX] = useState(0);
	const [tooltipY, setTooltipY] = useState(0);

	useEffect(() => {
		const handleSelectionChange = () => {
			// Clear any pending timeout
			if (selectionTimeoutRef.current) {
				clearTimeout(selectionTimeoutRef.current);
			}

			// Debounce the selection change
			selectionTimeoutRef.current = setTimeout(() => {
				const selection = window.getSelection();
				const text = selection.toString().trim();

				if (text && text.length > 0) {
					setSelectedText(text);

					try {
						const range = selection.getRangeAt(0);
						const rect = range.getBoundingClientRect();

						// Calculate tooltip position
						// Assuming tooltip height is around 50px and width is around 200px for initial calculation
						const tooltipHeight = 50;
						const tooltipWidth = 200;
						const padding = 10; // Distance from selection

						const x = rect.left + rect.width / 2 - tooltipWidth / 2;
						const y = rect.top - tooltipHeight - padding;

						setTooltipX(x);
						setTooltipY(y);
						setIsOpen(true);
					} catch (error) {
						console.warn("Failed to get selection range:", error);
						setIsOpen(false);
					}
				} else {
					setIsOpen(false);
				}
			}, 50);
		};

		const handleMouseUp = () => {
			setTimeout(handleSelectionChange, 10);
		};

		const handleClickOutside = (e) => {
			if (tooltipRef.current && !tooltipRef.current.contains(e.target)) {
				setIsOpen(false);
			}
		};

		document.addEventListener("mouseup", handleMouseUp);
		document.addEventListener("selectionchange", handleSelectionChange);
		document.addEventListener("mousedown", handleClickOutside);

		return () => {
			document.removeEventListener("mouseup", handleMouseUp);
			document.removeEventListener("selectionchange", handleSelectionChange);
			document.removeEventListener("mousedown", handleClickOutside);
			if (selectionTimeoutRef.current) {
				clearTimeout(selectionTimeoutRef.current);
			}
		};
	}, []);

	const handleHighlightClick = () => {
		if (handlers.onHighlight) {
			handlers.onHighlight(selectedText);
		}
		setIsOpen(false);
		window.getSelection().removeAllRanges();
	};

	const handleAskAIClick = () => {
		if (handlers.onAskAI) {
			handlers.onAskAI(selectedText);
		}
		setIsOpen(false);
		window.getSelection().removeAllRanges();
	};

	const setSelectionHandlers = useCallback((onHighlight, onAskAI) => {
		setHandlers({ onHighlight, onAskAI });
	}, []);

	return (
		<TextSelectionContext.Provider value={{ setSelectionHandlers }}>
			{children}
			{isOpen && (
				<div
					ref={tooltipRef}
					style={{
						position: "absolute",
						left: tooltipX,
						top: tooltipY,
						zIndex: 9999,
					}}
					className="relative"
				>
					{/* Subtle gradient background */}
					<div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 via-pink-600/20 to-orange-600/20 rounded-full blur-2xl" />

					{/* Main container with glassmorphism effect */}
					<div className="relative flex items-center gap-0.5 p-1 bg-white/10 dark:bg-gray-900/40 backdrop-blur-xl rounded-full shadow-2xl border border-white/20 dark:border-gray-700/30">
						<button
							type="button"
							onClick={handleHighlightClick}
							className="group flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-900 dark:text-white hover:bg-white/20 dark:hover:bg-white/10 rounded-full transition-all duration-200 hover:scale-105"
							title="Highlight"
						>
							<Highlighter className="w-3.5 h-3.5 transition-transform group-hover:rotate-12" />
							<span className="hidden sm:inline-block animate-in fade-in duration-200">
								Highlight
							</span>
						</button>

						<div className="w-px h-5 bg-gradient-to-b from-transparent via-gray-400/30 to-transparent dark:via-gray-600/30" />

						<button
							type="button"
							onClick={handleAskAIClick}
							className="group flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-900 dark:text-white hover:bg-white/20 dark:hover:bg-white/10 rounded-full transition-all duration-200 hover:scale-105"
							title="Ask AI"
						>
							<Sparkles className="w-3.5 h-3.5 transition-transform group-hover:rotate-12 group-hover:scale-110" />
							<span className="hidden sm:inline-block bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent font-semibold animate-in fade-in duration-200">
								Ask AI
							</span>
						</button>
					</div>
				</div>
			)}
		</TextSelectionContext.Provider>
	);
};

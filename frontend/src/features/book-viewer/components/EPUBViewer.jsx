import { useEffect, useRef, useState } from "react";
import { ReactReader } from "react-reader";
import "./EPUBViewer.css";

const EPUBViewer = ({ url, bookInfo }) => {
	const [location, setLocation] = useState(null);
	const [size, setSize] = useState(100);
	const renditionRef = useRef(null);
	const tocRef = useRef(null);
	const [showToc, setShowToc] = useState(false);

	useEffect(() => {
		if (renditionRef.current) {
			const handleKeyPress = (e) => {
				if (e.key === "ArrowLeft") {
					gotoPrevious();
				} else if (e.key === "ArrowRight") {
					gotoNext();
				}
			};

			document.addEventListener("keydown", handleKeyPress);
			return () => document.removeEventListener("keydown", handleKeyPress);
		}
	}, []);

	const locationChanged = (epubcifi) => {
		setLocation(epubcifi);

		// Save location to localStorage for persistence
		if (bookInfo?.id) {
			localStorage.setItem(`epub-location-${bookInfo.id}`, epubcifi);
		}
	};

	const onRendition = (rendition) => {
		renditionRef.current = rendition;

		// Apply theme
		const themes = rendition.themes;
		themes.default({
			"::selection": {
				background: "var(--primary)",
				color: "var(--primary-foreground)",
			},
			body: {
				color: "var(--foreground) !important",
				background: "var(--background) !important",
				"font-family": "system-ui, -apple-system, sans-serif",
				"line-height": "1.6",
				padding: "20px",
			},
			p: {
				margin: "1em 0",
			},
			"h1, h2, h3, h4, h5, h6": {
				color: "var(--foreground)",
				margin: "1em 0 0.5em",
			},
			a: {
				color: "var(--primary)",
				"text-decoration": "underline",
			},
			img: {
				"max-width": "100%",
				height: "auto",
			},
		});

		// Load saved location
		if (bookInfo?.id) {
			const savedLocation = localStorage.getItem(
				`epub-location-${bookInfo.id}`,
			);
			if (savedLocation) {
				setLocation(savedLocation);
			}
		}

		// Set font size
		rendition.themes.fontSize(`${size}%`);
	};

	const gotoPrevious = () => {
		if (renditionRef.current) {
			renditionRef.current.prev();
		}
	};

	const gotoNext = () => {
		if (renditionRef.current) {
			renditionRef.current.next();
		}
	};

	const increaseFontSize = () => {
		const newSize = Math.min(size + 10, 200);
		setSize(newSize);
		if (renditionRef.current) {
			renditionRef.current.themes.fontSize(`${newSize}%`);
		}
	};

	const decreaseFontSize = () => {
		const newSize = Math.max(size - 10, 50);
		setSize(newSize);
		if (renditionRef.current) {
			renditionRef.current.themes.fontSize(`${newSize}%`);
		}
	};

	const getToc = () => {
		if (tocRef.current) {
			return tocRef.current;
		}
		return [];
	};

	const handleTocSelect = (href) => {
		if (renditionRef.current) {
			renditionRef.current.display(href);
			setShowToc(false);
		}
	};

	return (
		<div className="epub-viewer-container">
			<div className="epub-controls-bar">
				<div className="epub-controls">
					<button
						type="button"
						onClick={() => setShowToc(!showToc)}
						className="epub-button"
					>
						{showToc ? "Hide" : "Show"} Table of Contents
					</button>
					<button
						type="button"
						onClick={decreaseFontSize}
						className="epub-button"
					>
						A-
					</button>
					<span className="font-size-display">{size}%</span>
					<button
						type="button"
						onClick={increaseFontSize}
						className="epub-button"
					>
						A+
					</button>
				</div>
			</div>

			{showToc && (
				<div className="epub-toc">
					<h3>Table of Contents</h3>
					<ul>
						{getToc().map((item, index) => (
							<li key={item.href || index}>
								<button
									type="button"
									onClick={() => handleTocSelect(item.href)}
									className="toc-item"
								>
									{item.label}
								</button>
							</li>
						))}
					</ul>
				</div>
			)}

			<div className="epub-reader-wrapper">
				<ReactReader
					url={url}
					location={location}
					locationChanged={locationChanged}
					getRendition={onRendition}
					tocChanged={(toc) => {
						tocRef.current = toc;
					}}
					epubOptions={{
						flow: "paginated",
						manager: "continuous",
					}}
				/>
			</div>
		</div>
	);
};

export default EPUBViewer;

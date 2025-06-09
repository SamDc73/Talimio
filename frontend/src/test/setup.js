import "@testing-library/jest-dom";

// Mock global objects and APIs
global.ResizeObserver = class {
	observe() {}
	unobserve() {}
	disconnect() {}
};

global.URL.createObjectURL = vi.fn();
global.URL.revokeObjectURL = vi.fn();

// Mock IntersectionObserver
global.IntersectionObserver = class {
	observe() {}
	unobserve() {}
	disconnect() {}
};

// Mock matchMedia
Object.defineProperty(window, "matchMedia", {
	writable: true,
	value: vi.fn().mockImplementation((query) => ({
		matches: false,
		media: query,
		onchange: null,
		addListener: vi.fn(),
		removeListener: vi.fn(),
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		dispatchEvent: vi.fn(),
	})),
});

import React, { createContext, useContext, useState, useMemo, useCallback } from "react";

// 1. Create the Context
const SidebarContext = createContext(null);

// 2. Create the Provider Component
export function SidebarProvider({ children }) {
  const [isOpen, setIsOpen] = useState(true); // Default to open

  // Wrap toggleSidebar in useCallback to give it a stable reference
  const toggleSidebar = useCallback(() => {
    setIsOpen((prevIsOpen) => !prevIsOpen);
  }, []); // No dependencies needed for setIsOpen

  // Memoize the context value to prevent unnecessary re-renders
  const value = useMemo(
    () => ({
      isOpen,
      toggleSidebar, // Now toggleSidebar has a stable reference
    }),
    [isOpen, toggleSidebar], // Include toggleSidebar in dependencies
  );

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
}

// 3. Create the Custom Hook
export function useSidebar() {
  const context = useContext(SidebarContext);
  if (context === null) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
}

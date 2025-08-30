import type { FC, ReactNode } from 'react';

/**
 * Centralized debug utilities for the application.
 * Vite will automatically tree-shake debug calls in production when DEBUG is false.
 */

// Convert string to boolean and ensure it's only enabled in development by default
const DEBUG = import.meta.env.VITE_DEBUG_MODE === "true" && import.meta.env.DEV;

/**
 * Debug logging utilities that are automatically removed in production builds
 */
export const debug = {
  /**
   * Log debug information
   */
  log: DEBUG
    ? (...args: unknown[]) => console.log("🐛 [DEBUG]", ...args)
    : () => {},

  /**
   * Log debug warnings
   */
  warn: DEBUG
    ? (...args: unknown[]) => console.warn("⚠️ [DEBUG]", ...args)
    : () => {},

  /**
   * Log debug errors
   */
  error: DEBUG
    ? (...args: unknown[]) => console.error("❌ [DEBUG]", ...args)
    : () => {},

  /**
   * Display data in table format
   */
  table: DEBUG
    ? (data: unknown) => console.table(data)
    : () => {},

  /**
   * Start performance timer
   */
  time: DEBUG
    ? (label: string) => console.time(`⏱️ [DEBUG] ${label}`)
    : () => {},

  /**
   * End performance timer
   */
  timeEnd: DEBUG
    ? (label: string) => console.timeEnd(`⏱️ [DEBUG] ${label}`)
    : () => {},

  /**
   * Group console logs
   */
  group: DEBUG
    ? (label: string) => console.group(`📂 [DEBUG] ${label}`)
    : () => {},

  /**
   * End console group
   */
  groupEnd: DEBUG
    ? () => console.groupEnd()
    : () => {},

  /**
   * Conditional debug - only executes callback if debug is enabled
   */
  run: DEBUG
    ? <T>(callback: () => T): T => callback()
    : () => undefined as any,
};

/**
 * Debug flag for conditional logic
 */
export const isDebug = DEBUG;

/**
 * Dynamically import debug utilities only when debug is enabled
 */
export const loadDebugUtils = async () => {
  if (DEBUG) {
    try {
      const { default: authTest } = await import("../utils/authTest.js");
      debug.log("Debug utilities loaded");
      return authTest;
    } catch (error) {
      debug.error("Failed to load debug utilities:", error);
    }
  }
  return null;
};

/**
 * Debug component wrapper - only renders children in debug mode
 */
export const DebugOnly: FC<{ children: ReactNode }> = ({ children }) => {
  return DEBUG ? <>{children}</> : null;
};
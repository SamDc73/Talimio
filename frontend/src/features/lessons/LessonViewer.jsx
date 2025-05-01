import { Button } from "@/components/button";
import { cn, convertMarkdownToHtml } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";
import React from "react";
import "./LessonViewer.css";

/**
 * Component to display a lesson
 *
 * @param {Object} props
 * @param {Object} props.lesson - The lesson to display
 * @param {boolean} props.isLoading - Whether the lesson is loading
 * @param {string} props.error - Error message if any
 * @param {Function} props.onBack - Function to call when back button is clicked
 * @returns {JSX.Element}
 */
export function LessonViewer({ lesson, isLoading, error, onBack }) {
  // Handle loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500 mb-4" />
        <p>Loading lesson...</p>
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-red-600">
        <div className="max-w-2xl mx-auto p-6 bg-red-50 rounded-lg border border-red-200">
          <h2 className="text-xl font-semibold mb-4">Error loading lesson</h2>
          <p className="mb-4">{error}</p>
          <Button onClick={onBack} variant="outline" className="flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to outline
          </Button>
        </div>
      </div>
    );
  }

  // Handle no lesson state
  if (!lesson) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500">
        <div className="max-w-2xl mx-auto p-6 bg-zinc-50 rounded-lg border border-zinc-200">
          <h2 className="text-xl font-semibold mb-4">No lesson selected</h2>
          <p className="mb-4">Please select a lesson from the outline to view its content.</p>
          <Button onClick={onBack} variant="outline" className="flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to outline
          </Button>
        </div>
      </div>
    );
  }

  // Render the lesson content
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <Button onClick={onBack} variant="outline" className="flex items-center gap-2">
          <ArrowLeft className="w-4 h-4" />
          Back to outline
        </Button>
      </div>

      {/* Lesson content */}
      <div className="prose prose-emerald max-w-none">
        {/* Use dangerouslySetInnerHTML only if you have sanitized the content or trust the source */}
        <div
          className="markdown-content"
          dangerouslySetInnerHTML={{ __html: convertMarkdownToHtml(lesson.md_source) }}
        />
      </div>
    </div>
  );
}

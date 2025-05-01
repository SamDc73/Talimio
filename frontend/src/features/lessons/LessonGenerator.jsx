import { Button } from "@/components/button";
import { useToast } from "@/hooks/use-toast";
import React, { useState } from "react";
import { useGenerateLesson } from "../hooks/useGenerateLesson";

/**
 * Component to generate and display a lesson for a roadmap node.
 */
export function LessonGenerator({ courseId, slug, nodeMeta }) {
  const { data: lesson, isLoading, error, generate } = useGenerateLesson();
  const { toast } = useToast();

  const handleGenerate = async () => {
    try {
      await generate({ courseId, slug, nodeMeta });
      toast({ title: "Lesson generated", description: `Lesson for ${slug}` });
    } catch {
      toast({ title: "Error", description: "Failed to generate lesson", variant: "destructive" });
    }
  };

  return (
    <div className="border rounded-lg p-4">
      <Button onClick={handleGenerate} disabled={isLoading}>
        {isLoading ? "Generating..." : "Generate Lesson"}
      </Button>
      {error && <div className="text-red-600 mt-2">{error}</div>}
      {lesson && <pre className="whitespace-pre-wrap mt-4 bg-gray-100 p-2 rounded">{lesson.md_source}</pre>}
    </div>
  );
}

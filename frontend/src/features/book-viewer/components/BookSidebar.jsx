import { useState } from "react";
import { BookOpen, ChevronRight, Circle, CheckCircle, FileText } from "lucide-react";
import { useSidebar } from "../../navigation/SidebarContext";

function BookSidebar({ book, currentPage = 1, onChapterClick }) {
  const { isOpen } = useSidebar();
  const [expandedChapters, setExpandedChapters] = useState([0]); // Expand first chapter by default
  const [completedSections, setCompletedSections] = useState(new Set());

  if (!book) return null;

  // Mock chapters structure - this can be replaced with real data when available
  const mockChapters = [
    {
      id: "ch1",
      title: "Introduction",
      startPage: 1,
      endPage: 20,
      sections: [
        { id: "s1-1", title: "Getting Started", page: 1 },
        { id: "s1-2", title: "Basic Concepts", page: 8 },
        { id: "s1-3", title: "Overview", page: 15 }
      ]
    },
    {
      id: "ch2",
      title: "Chapter 2: Core Concepts",
      startPage: 21,
      endPage: 45,
      sections: [
        { id: "s2-1", title: "Fundamental Principles", page: 21 },
        { id: "s2-2", title: "Advanced Topics", page: 30 },
        { id: "s2-3", title: "Practical Examples", page: 38 }
      ]
    },
    {
      id: "ch3",
      title: "Chapter 3: Implementation",
      startPage: 46,
      endPage: 80,
      sections: [
        { id: "s3-1", title: "Setup and Configuration", page: 46 },
        { id: "s3-2", title: "Best Practices", page: 60 },
        { id: "s3-3", title: "Common Patterns", page: 70 }
      ]
    }
  ];

  const handleToggleChapter = (chapterIndex) => {
    setExpandedChapters((prev) =>
      prev.includes(chapterIndex) 
        ? prev.filter((idx) => idx !== chapterIndex) 
        : [...prev, chapterIndex]
    );
  };

  const handleSectionClick = (sectionId, pageNumber) => {
    setCompletedSections(prev => new Set([...prev, sectionId]));
    if (onChapterClick) {
      onChapterClick(pageNumber);
    }
  };

  const getChapterProgress = (chapter) => {
    const completedCount = chapter.sections.filter(s => completedSections.has(s.id)).length;
    return (completedCount / chapter.sections.length) * 100;
  };

  const isPageInRange = (page, start, end) => {
    return page >= start && page <= end;
  };

  // Calculate overall progress
  const totalSections = mockChapters.reduce((acc, ch) => acc + ch.sections.length, 0);
  const completedCount = completedSections.size;
  const overallProgress = Math.round((completedCount / totalSections) * 100);

  return (
    <aside
      className={`fixed-sidebar flex flex-col bg-white border-r border-zinc-200 transition-all duration-300 ease-in-out ${
        isOpen ? "w-[320px] opacity-100 translate-x-0" : "w-0 opacity-0 -translate-x-full"
      }`}
      style={{ boxShadow: isOpen ? "0 4px 20px rgba(0, 0, 0, 0.05)" : "none" }}
    >
      {/* Book header */}
      <div
        className={`px-4 pt-20 pb-4 border-b border-zinc-100 transition-opacity duration-300 ${
          isOpen ? "opacity-100" : "opacity-0"
        }`}
      >
        <div className="flex items-start gap-3 mb-3">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <BookOpen className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-zinc-900 text-sm line-clamp-2">
              {book.title}
            </h3>
            <p className="text-xs text-zinc-600 mt-1">{book.author}</p>
          </div>
        </div>

        {/* Progress indicator */}
        <div className="flex items-center gap-2">
          <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full px-3 py-1">
            {overallProgress}% Read
          </span>
          <span className="text-xs text-zinc-500">
            Page {currentPage} of {book.total_pages || "?"}
          </span>
        </div>
      </div>

      {/* Chapters list */}
      <nav
        className={`flex-1 p-3 space-y-4 overflow-y-auto transition-opacity duration-300 ${
          isOpen ? "opacity-100" : "opacity-0"
        }`}
      >
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-2">
          Table of Contents
        </h4>
        
        {mockChapters.map((chapter, chapterIndex) => {
          const isExpanded = expandedChapters.includes(chapterIndex);
          const chapterProgress = getChapterProgress(chapter);
          const isCurrentChapter = isPageInRange(currentPage, chapter.startPage, chapter.endPage);
          
          return (
            <div 
              key={chapter.id} 
              className={`rounded-2xl border ${
                isCurrentChapter ? "border-emerald-200 bg-emerald-50/50" : "border-zinc-200 bg-white"
              } shadow-sm overflow-hidden`}
            >
              {/* Chapter header */}
              <button
                type="button"
                onClick={() => handleToggleChapter(chapterIndex)}
                className="flex items-center gap-3 justify-between w-full px-4 py-3 text-left font-semibold text-base text-zinc-900 border-b border-zinc-100 rounded-t-2xl focus:outline-none"
                style={{ background: isCurrentChapter ? "transparent" : "#fff" }}
                aria-expanded={isExpanded}
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="relative flex items-center justify-center">
                    <div className="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center">
                      <span className="text-sm text-zinc-600">{chapterIndex + 1}</span>
                    </div>
                    {/* Progress circle */}
                    {chapterProgress > 0 && (
                      <svg
                        className="absolute top-0 left-0 w-8 h-8 -rotate-90"
                        role="img"
                        aria-label={`Chapter progress: ${Math.round(chapterProgress)}%`}
                      >
                        <title>Chapter progress indicator</title>
                        <circle
                          cx="16"
                          cy="16"
                          r="14"
                          strokeWidth="2.5"
                          fill="none"
                          stroke="#f4f4f5"
                          className="opacity-70"
                        />
                        <circle
                          cx="16"
                          cy="16"
                          r="14"
                          strokeWidth="2.5"
                          fill="none"
                          stroke="#10b981"
                          strokeLinecap="round"
                          strokeDasharray={`${(chapterProgress / 100) * 87.96} 87.96`}
                          className="transition-all duration-300"
                          style={{
                            filter: "drop-shadow(0 1px 1px rgb(0 0 0 / 0.05))",
                          }}
                        />
                      </svg>
                    )}
                  </div>
                  <span className="line-clamp-2 text-sm">{chapter.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500">p. {chapter.startPage}</span>
                  <ChevronRight
                    className={`w-5 h-5 text-zinc-400 transition-transform duration-200 ${
                      isExpanded ? "rotate-90 text-emerald-600" : "rotate-0"
                    }`}
                  />
                </div>
              </button>

              {/* Chapter sections */}
              {isExpanded && (
                <ol className="px-4 py-2 space-y-2">
                  {chapter.sections.map((section) => {
                    const isCompleted = completedSections.has(section.id);
                    const isCurrentSection = currentPage === section.page;
                    
                    return (
                      <li key={section.id} className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSectionClick(section.id, section.page);
                          }}
                          className="mt-0.5 transition-all duration-200 hover:scale-110"
                        >
                          {isCompleted ? (
                            <CheckCircle className="w-5 h-5 text-emerald-500" />
                          ) : (
                            <Circle className="w-5 h-5 text-zinc-300 hover:text-emerald-300" />
                          )}
                        </button>
                        <button
                          type="button"
                          className={`text-left flex-1 min-w-0 ${
                            isCompleted
                              ? "font-semibold text-emerald-700"
                              : isCurrentSection
                              ? "font-semibold text-emerald-700"
                              : "text-zinc-800"
                          }`}
                          style={{
                            background: "none",
                            border: "none",
                            padding: 0,
                            cursor: "pointer",
                          }}
                          onClick={() => handleSectionClick(section.id, section.page)}
                        >
                          <span className="line-clamp-2 text-sm">{section.title}</span>
                          <span className="text-xs text-zinc-500 ml-2">p. {section.page}</span>
                        </button>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>
          );
        })}

        {/* Book metadata section */}
        <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden mt-6">
          <div className="px-4 py-3 border-b border-zinc-100">
            <h4 className="font-semibold text-sm text-zinc-900 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Book Details
            </h4>
          </div>
          <div className="px-4 py-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-zinc-600">Pages</span>
              <span className="text-zinc-900">{book.total_pages || "Unknown"}</span>
            </div>
            {book.publication_year && (
              <div className="flex justify-between">
                <span className="text-zinc-600">Published</span>
                <span className="text-zinc-900">{book.publication_year}</span>
              </div>
            )}
            {book.language && (
              <div className="flex justify-between">
                <span className="text-zinc-600">Language</span>
                <span className="text-zinc-900">{book.language}</span>
              </div>
            )}
            {book.isbn && (
              <div className="flex justify-between">
                <span className="text-zinc-600">ISBN</span>
                <span className="text-zinc-900 text-xs">{book.isbn}</span>
              </div>
            )}
          </div>
        </div>
      </nav>
    </aside>
  );
}

export default BookSidebar;
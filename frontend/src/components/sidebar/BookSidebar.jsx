import { useState } from "react";
import { FileText } from "lucide-react";
import SidebarContainer from "./SidebarContainer";
import ProgressIndicator from "./ProgressIndicator";
import SidebarNav from "./SidebarNav";
import ExpandableSection from "./ExpandableSection";
import ProgressCircle from "./ProgressCircle";
import CompletionCheckbox from "./CompletionCheckbox";
import SidebarItem from "./SidebarItem";

function BookSidebar({ book, currentPage = 1, onChapterClick }) {
  const [expandedChapters, setExpandedChapters] = useState([0]);
  const [completedSections, setCompletedSections] = useState(new Set());

  if (!book) return null;

  const chapters = book.table_of_contents || [];

  if (!chapters.length) {
    return (
      <SidebarContainer>
        <div className="px-4 pt-20 pb-4">
          <div className="text-center text-zinc-500 text-sm mt-8">
            <FileText className="w-12 h-12 mx-auto mb-4 text-zinc-300" />
            <p>No table of contents available</p>
            <p className="text-xs mt-2">This book doesn't have chapter information.</p>
          </div>
        </div>
      </SidebarContainer>
    );
  }

  const handleToggleChapter = (chapterIndex) => {
    setExpandedChapters((prev) =>
      prev.includes(chapterIndex) ? prev.filter((idx) => idx !== chapterIndex) : [...prev, chapterIndex]
    );
  };

  const handleSectionClick = (sectionId, pageNumber) => {
    setCompletedSections((prev) => new Set([...prev, sectionId]));
    if (onChapterClick) {
      onChapterClick(pageNumber);
    }
  };

  const getChapterProgress = (chapter) => {
    if (!chapter.children || chapter.children.length === 0) return 0;
    const completedCount = chapter.children.filter((s) => completedSections.has(s.id)).length;
    return (completedCount / chapter.children.length) * 100;
  };

  const isPageInRange = (page, chapter) => {
    if (chapter.start_page && chapter.end_page) {
      return page >= chapter.start_page && page <= chapter.end_page;
    }
    return page === chapter.page;
  };

  const countAllSections = (chapters) => {
    let count = 0;
    for (const ch of chapters) {
      if (ch.children && ch.children.length > 0) {
        count += ch.children.length;
      } else {
        count += 1;
      }
    }
    return count;
  };

  const totalSections = countAllSections(chapters);
  const completedCount = completedSections.size;
  const overallProgress = totalSections > 0 ? Math.round((completedCount / totalSections) * 100) : 0;

  return (
    <SidebarContainer>
      <ProgressIndicator progress={overallProgress} suffix="Read">
        <span className="text-xs text-zinc-500">
          Page {currentPage} of {book.total_pages || "?"}
        </span>
      </ProgressIndicator>

      <SidebarNav>
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-2">Table of Contents</h4>

        {chapters.map((chapter, chapterIndex) => {
          const isExpanded = expandedChapters.includes(chapterIndex);
          const chapterProgress = getChapterProgress(chapter);
          const isCurrentChapter = isPageInRange(currentPage, chapter);

          return (
            <ExpandableSection
              key={chapter.id}
              title={chapter.title}
              isExpanded={isExpanded}
              onToggle={() => handleToggleChapter(chapterIndex)}
              isActive={isCurrentChapter}
              headerContent={
                <div
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onChapterClick) {
                      onChapterClick(chapter.page || chapter.start_page);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      e.stopPropagation();
                      if (onChapterClick) {
                        onChapterClick(chapter.page || chapter.start_page);
                      }
                    }
                  }}
                  role="link"
                  tabIndex={0}
                  className="cursor-pointer hover:text-emerald-700 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 rounded"
                >
                  <ProgressCircle number={chapterIndex + 1} progress={chapterProgress} />
                </div>
              }
            >
              {chapter.children && chapter.children.length > 0 && (
                <ol>
                  {chapter.children.map((section) => {
                    const isCompleted = completedSections.has(section.id);
                    const isCurrentSection = currentPage === section.page;

                    return (
                      <SidebarItem
                        key={section.id}
                        title={
                          <>
                            <span className="line-clamp-2 text-sm">{section.title}</span>
                            <span className="text-xs text-zinc-500 ml-2">p. {section.page}</span>
                          </>
                        }
                        isActive={isCurrentSection}
                        isCompleted={isCompleted}
                        onClick={() => handleSectionClick(section.id, section.page)}
                        leftContent={
                          <CompletionCheckbox
                            isCompleted={isCompleted}
                            onClick={() => handleSectionClick(section.id, section.page)}
                          />
                        }
                      />
                    );
                  })}
                </ol>
              )}
            </ExpandableSection>
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
      </SidebarNav>
    </SidebarContainer>
  );
}

export default BookSidebar;
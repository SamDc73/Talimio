import { useState, useEffect } from "react";
import { FileText, Download } from "lucide-react";
import SidebarContainer from "./SidebarContainer";
import ProgressIndicator from "./ProgressIndicator";
import SidebarNav from "./SidebarNav";
import ExpandableSection from "./ExpandableSection";
import ProgressCircle from "./ProgressCircle";
import CompletionCheckbox from "./CompletionCheckbox";
import SidebarItem from "./SidebarItem";
import { getBookChapters, updateChapterStatus, extractBookChapters } from "@/services/booksService";
import { useToast } from "@/hooks/use-toast";

function BookSidebar({ book, currentPage = 1, onChapterClick }) {
  const [expandedChapters, setExpandedChapters] = useState([0]);
  const [completedSections, setCompletedSections] = useState(new Set());
  const [apiChapters, setApiChapters] = useState([]);
  const [isLoadingChapters, setIsLoadingChapters] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const { toast } = useToast();

  // Fetch chapters from API
  useEffect(() => {
    if (!book?.id) return;

    async function fetchChapters() {
      setIsLoadingChapters(true);
      try {
        const chapters = await getBookChapters(book.id);
        setApiChapters(chapters || []);
        
        // Update completed sections based on chapter status
        const completed = new Set();
        chapters?.forEach(chapter => {
          if (chapter.status === 'completed') {
            completed.add(chapter.id);
          }
        });
        setCompletedSections(completed);
      } catch (error) {
        console.error('Failed to fetch chapters:', error);
        // Fall back to table of contents if API fails
        setApiChapters([]);
      } finally {
        setIsLoadingChapters(false);
      }
    }

    fetchChapters();
  }, [book?.id]);

  const handleExtractChapters = async () => {
    setIsExtracting(true);
    try {
      const result = await extractBookChapters(book.id);
      toast({
        title: "Chapters extracted",
        description: `Successfully extracted ${result.count || 0} chapters`,
      });
      
      // Refresh chapters
      const chapters = await getBookChapters(book.id);
      setApiChapters(chapters || []);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to extract chapters",
        variant: "destructive",
      });
    } finally {
      setIsExtracting(false);
    }
  };

  if (!book) return null;

  // Use API chapters if available, otherwise fall back to table of contents
  const chapters = apiChapters.length > 0 ? apiChapters : (book.table_of_contents || []);

  if (!chapters.length) {
    return (
      <SidebarContainer>
        <div className="px-4 pt-20 pb-4">
          <div className="text-center text-zinc-500 text-sm mt-8">
            <FileText className="w-12 h-12 mx-auto mb-4 text-zinc-300" />
            <p>No table of contents available</p>
            <p className="text-xs mt-2">This book doesn't have chapter information.</p>
            
            {/* Extract chapters button */}
            <button
              type="button"
              onClick={handleExtractChapters}
              disabled={isExtracting}
              className="mt-4 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
            >
              <Download className="w-4 h-4" />
              {isExtracting ? 'Extracting...' : 'Extract Chapters'}
            </button>
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

  const handleSectionClick = async (section, pageNumber) => {
    const sectionId = section.id || section.chapter_id;
    const isCompleted = completedSections.has(sectionId);
    const newStatus = isCompleted ? 'not_started' : 'completed';

    // Optimistic update
    setCompletedSections((prev) => {
      const newSet = new Set(prev);
      if (isCompleted) {
        newSet.delete(sectionId);
      } else {
        newSet.add(sectionId);
      }
      return newSet;
    });

    // Update via API if this is an API chapter
    if (apiChapters.length > 0 && section.chapter_id) {
      try {
        await updateChapterStatus(book.id, section.chapter_id, newStatus);
        toast({
          title: "Chapter updated",
          description: `Chapter marked as ${newStatus.replace('_', ' ')}`,
        });
      } catch (error) {
        // Revert optimistic update
        setCompletedSections((prev) => {
          const newSet = new Set(prev);
          if (isCompleted) {
            newSet.add(sectionId);
          } else {
            newSet.delete(sectionId);
          }
          return newSet;
        });
        
        toast({
          title: "Error",
          description: "Failed to update chapter status",
          variant: "destructive",
        });
      }
    }

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
                        onClick={() => handleSectionClick(section, section.page)}
                        leftContent={
                          <CompletionCheckbox
                            isCompleted={isCompleted}
                            onClick={() => handleSectionClick(section, section.page)}
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
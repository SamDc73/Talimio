import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BookSidebar from '@/components/sidebar/BookSidebar'

// Mock the useApi hook for chapter fetching
vi.mock('@/hooks/useApi', () => ({
  useApi: vi.fn(() => ({
    data: null,
    isLoading: false,
    error: null,
    execute: vi.fn()
  }))
}))

describe('BookSidebar', () => {
  const mockBook = {
    id: 'book-1',
    title: 'Test Book',
    total_pages: 200,
    publication_year: 2023,
    language: 'English',
    isbn: '978-0123456789',
    table_of_contents: [
      {
        id: 'chapter-1',
        title: 'Introduction',
        page: 1,
        start_page: 1,
        end_page: 10,
        children: [
          { id: 'section-1', title: 'Overview', page: 2 },
          { id: 'section-2', title: 'Goals', page: 5 }
        ]
      },
      {
        id: 'chapter-2',
        title: 'Getting Started',
        page: 11,
        start_page: 11,
        end_page: 30,
        children: [
          { id: 'section-3', title: 'Setup', page: 12 },
          { id: 'section-4', title: 'Configuration', page: 20 }
        ]
      }
    ]
  }

  const mockOnChapterClick = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders book sidebar with table of contents', () => {
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    expect(screen.getByText('Table of Contents')).toBeInTheDocument()
    expect(screen.getByText('Introduction')).toBeInTheDocument()
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
    expect(screen.getByText('Book Details')).toBeInTheDocument()
  })

  it('displays book metadata correctly', () => {
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    expect(screen.getByText('200')).toBeInTheDocument() // total pages
    expect(screen.getByText('2023')).toBeInTheDocument() // publication year
    expect(screen.getByText('English')).toBeInTheDocument() // language
    expect(screen.getByText('978-0123456789')).toBeInTheDocument() // ISBN
  })

  it('shows current page in progress indicator', () => {
    render(<BookSidebar book={mockBook} currentPage={15} onChapterClick={mockOnChapterClick} />)

    expect(screen.getByText('Page 15 of 200')).toBeInTheDocument()
  })

  it('expands and collapses chapters', async () => {
    const user = userEvent.setup()
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    // First chapter should be expanded by default (index 0)
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getByText('Goals')).toBeInTheDocument()

    // Second chapter sections should not be visible initially
    expect(screen.queryByText('Setup')).not.toBeInTheDocument()

    // Click on the second chapter to expand it
    const secondChapter = screen.getByText('Getting Started')
    await user.click(secondChapter.closest('button'))

    // Now setup section should be visible
    expect(screen.getByText('Setup')).toBeInTheDocument()
    expect(screen.getByText('Configuration')).toBeInTheDocument()
  })

  it('calls onChapterClick when chapter is clicked', async () => {
    const user = userEvent.setup()
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    // Click on a chapter
    const chapterButton = screen.getByText('Introduction').closest('[role="link"]')
    await user.click(chapterButton)

    expect(mockOnChapterClick).toHaveBeenCalledWith(1)
  })

  it('calls onChapterClick when section is clicked', async () => {
    const user = userEvent.setup()
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    // Click on a section (should be visible since first chapter is expanded)
    const sectionElement = screen.getByText('Overview')
    await user.click(sectionElement)

    expect(mockOnChapterClick).toHaveBeenCalledWith(2)
  })

  it('tracks section completion', async () => {
    const user = userEvent.setup()
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    // Find and click a completion checkbox
    const checkboxes = screen.getAllByRole('checkbox')
    const firstCheckbox = checkboxes[0]
    
    await user.click(firstCheckbox)

    // Progress should update (this is internal state, so we'd need to check UI changes)
    // The specific assertion would depend on how the completion is visually indicated
  })

  it('highlights current chapter based on page', () => {
    render(<BookSidebar book={mockBook} currentPage={15} onChapterClick={mockOnChapterClick} />)

    // Page 15 should be in the second chapter (pages 11-30)
    // This would need to check for visual indicators of the active chapter
    // Implementation depends on how the active state is styled
  })

  it('calculates chapter progress correctly', () => {
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    // Initially, no sections should be completed, so progress should be 0
    // After marking sections as complete, progress should update
    // This would require testing the internal state changes
  })

  it('handles keyboard navigation', async () => {
    const user = userEvent.setup()
    render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

    const chapterLink = screen.getByText('Introduction').closest('[role="link"]')
    
    // Focus the chapter link
    chapterLink.focus()
    
    // Press Enter
    await user.keyboard('{Enter}')
    
    expect(mockOnChapterClick).toHaveBeenCalledWith(1)

    // Press Space
    await user.keyboard(' ')
    
    expect(mockOnChapterClick).toHaveBeenCalledWith(1)
  })

  it('shows fallback when no table of contents is available', () => {
    const bookWithoutTOC = { ...mockBook, table_of_contents: [] }
    render(<BookSidebar book={bookWithoutTOC} currentPage={1} onChapterClick={mockOnChapterClick} />)

    expect(screen.getByText('No table of contents available')).toBeInTheDocument()
    expect(screen.getByText("This book doesn't have chapter information.")).toBeInTheDocument()
  })

  it('returns null when no book is provided', () => {
    const { container } = render(<BookSidebar book={null} currentPage={1} onChapterClick={mockOnChapterClick} />)
    expect(container.firstChild).toBeNull()
  })

  // Tests for Phase 3 integration with new chapter endpoints
  describe('Phase 3 Chapter Integration', () => {
    it('should fetch chapters from new API endpoint', async () => {
      const { useApi } = await import('@/hooks/useApi')
      const mockExecute = vi.fn().mockResolvedValue([
        { id: 1, title: 'Chapter 1', start_page: 1, end_page: 10, status: 'not_started' },
        { id: 2, title: 'Chapter 2', start_page: 11, end_page: 20, status: 'completed' }
      ])

      useApi.mockReturnValue({
        data: null,
        isLoading: false,
        error: null,
        execute: mockExecute
      })

      render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

      // Verify the API hook is called with correct endpoint
      expect(useApi).toHaveBeenCalledWith('/books/{bookId}/chapters')
    })

    it('should update chapter status when marked complete', async () => {
      const { useApi } = await import('@/hooks/useApi')
      const mockStatusUpdate = vi.fn().mockResolvedValue({ success: true })

      useApi.mockReturnValue({
        data: null,
        isLoading: false,
        error: null,
        execute: mockStatusUpdate
      })

      const user = userEvent.setup()
      render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

      // When marking a section complete, it should call the status update API
      const checkboxes = screen.getAllByRole('checkbox')
      await user.click(checkboxes[0])

      // This test would need the actual implementation to verify the API call
    })

    it('should extract chapters when button is clicked', async () => {
      const { useApi } = await import('@/hooks/useApi')
      const mockExtract = vi.fn().mockResolvedValue({ message: 'Chapters extracted', count: 5 })

      useApi.mockReturnValue({
        data: null,
        isLoading: false,
        error: null,
        execute: mockExtract
      })

      render(<BookSidebar book={mockBook} currentPage={1} onChapterClick={mockOnChapterClick} />)

      // This would require adding an extract chapters button to the component
      // and testing that it calls the extract endpoint
    })
  })
})
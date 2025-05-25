import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import PDFViewer from './components/PDFViewer';
import EPUBViewer from './components/EPUBViewer';
import { SidebarProvider, useSidebar } from '../navigation/SidebarContext';
import BookSidebar from './components/BookSidebar';
import { BookHeader } from '@/components/header/BookHeader';
import './BookViewer.css';

const BookViewerContent = () => {
  const { bookId } = useParams();
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(100);
  const pdfViewerRef = useRef(null);
  const { isOpen, toggle } = useSidebar();

  useEffect(() => {
    const fetchBook = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/v1/books/${bookId}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch book: ${response.statusText}`);
        }
        const data = await response.json();
        setBook(data);
        setTotalPages(data.total_pages || 0);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchBook();
  }, [bookId]);


  const handlePageChange = (pageNum) => {
    setCurrentPage(pageNum);
  };

  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 20, 300));
  };

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 20, 50));
  };

  const handleZoomChange = (newZoom) => {
    setZoomLevel(newZoom);
  };

  const handleFitToScreen = () => {
    if (pdfViewerRef.current?.calculateFitToWidth) {
      pdfViewerRef.current.calculateFitToWidth();
    }
  };

  if (loading) {
    return (
      <div className="book-viewer-loading">
        <div className="spinner">Loading book...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="book-viewer-error">
        <h2>Error loading book</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!book) {
    return (
      <div className="book-viewer-error">
        <h2>Book not found</h2>
      </div>
    );
  }

  const fileType = book.file_type?.toLowerCase();
  const bookUrl = `/api/v1/books/${bookId}/file`;

  return (
    <div className="flex h-screen bg-background">
      <BookHeader
        bookTitle={book.title}
        bookAuthor={book.author}
        currentPage={currentPage}
        totalPages={totalPages}
        isOpen={isOpen}
        toggleSidebar={toggle}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onFitToScreen={handleFitToScreen}
        zoomLevel={zoomLevel}
        showZoomControls={fileType === 'pdf'}
      />
      
      <BookSidebar 
        book={book} 
        currentPage={currentPage}
        onChapterClick={(pageNumber) => {
          // For PDF, we need to scroll to the page
          if (fileType === 'pdf' && pdfViewerRef.current) {
            pdfViewerRef.current.scrollToPage?.(pageNumber);
          }
          // For EPUB, we would need to implement navigation
        }}
      />
      
      <main className={`flex-1 transition-all duration-300 ${isOpen ? 'ml-64' : 'ml-0'} pt-16`}>
        <div className="book-viewer-container h-full">
          {fileType === 'pdf' ? (
            <PDFViewer 
              ref={pdfViewerRef}
              url={bookUrl} 
              bookInfo={book}
              onPageChange={handlePageChange}
              zoom={zoomLevel}
              onZoomChange={handleZoomChange}
            />
          ) : fileType === 'epub' ? (
            <EPUBViewer 
              url={bookUrl} 
              bookInfo={book}
            />
          ) : (
            <div className="book-viewer-error">
              <h2>Unsupported file format</h2>
              <p>Only PDF and EPUB files are supported.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

const BookViewer = () => {
  return (
    <SidebarProvider>
      <BookViewerContent />
    </SidebarProvider>
  );
};

export default BookViewer;
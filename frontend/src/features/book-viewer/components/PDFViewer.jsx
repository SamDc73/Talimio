import { useState, useEffect, useRef, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import './PDFViewer.css';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const PDFViewer = forwardRef(({ url, bookInfo, onPageChange, zoom = 100, onZoomChange }, ref) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [visiblePages, setVisiblePages] = useState(new Set([1, 2, 3]));
  const [pageWidth, setPageWidth] = useState(null);
  const containerRef = useRef(null);
  const documentRef = useRef(null);
  const pagesRef = useRef({});
  const scale = zoom / 100;

  // Memoize document options to prevent re-renders
  const documentOptions = useMemo(() => ({
    cMapUrl: 'cmaps/',
    cMapPacked: true,
  }), []);

  const onDocumentLoadSuccess = (pdf) => {
    setNumPages(pdf.numPages);
    // Get the first page to determine its width
    pdf.getPage(1).then(page => {
      const viewport = page.getViewport({ scale: 1 });
      setPageWidth(viewport.width);
    });
    if (onPageChange) {
      onPageChange(1);
    }
  };

  // Calculate fit to width scale
  const calculateFitToWidth = useCallback(() => {
    if (!containerRef.current || !pageWidth) return;
    
    const containerWidth = containerRef.current.clientWidth;
    const padding = 160; // Account for padding and margins (increased for transform scaling)
    const availableWidth = containerWidth - padding;
    const newScale = (availableWidth / pageWidth) * 100;
    
    if (onZoomChange) {
      onZoomChange(Math.round(newScale));
    }
  }, [pageWidth, onZoomChange]);

  const scrollToPage = useCallback((pageNum) => {
    const pageElement = pagesRef.current[pageNum];
    if (pageElement && containerRef.current) {
      // Pre-render the target page and adjacent ones
      setVisiblePages(prev => new Set([...prev, pageNum - 1, pageNum, pageNum + 1]));
      
      requestAnimationFrame(() => {
        pageElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }, []);

  // Expose methods to parent component
  useImperativeHandle(ref, () => ({
    calculateFitToWidth,
    scrollToPage
  }), [calculateFitToWidth, scrollToPage]);

  // Handle wheel zoom and keyboard detection
  useEffect(() => {
    const handleWheel = (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -10 : 10;
        const newZoom = Math.max(50, Math.min(300, zoom + delta));
        if (onZoomChange) {
          onZoomChange(newZoom);
        }
      }
    };

    const handleKeyDown = (e) => {
      if (e.ctrlKey || e.metaKey) {
        containerRef.current?.classList.add('zoom-ready');
      }
    };

    const handleKeyUp = (e) => {
      if (!e.ctrlKey && !e.metaKey) {
        containerRef.current?.classList.remove('zoom-ready');
      }
    };

    const container = containerRef.current;
    if (container) {
      container.addEventListener('wheel', handleWheel, { passive: false });
      document.addEventListener('keydown', handleKeyDown);
      document.addEventListener('keyup', handleKeyUp);
    }

    return () => {
      if (container) {
        container.removeEventListener('wheel', handleWheel);
      }
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('keyup', handleKeyUp);
    };
  }, [zoom, onZoomChange]);

  // Intersection Observer for efficient page visibility detection
  useEffect(() => {
    if (!numPages || !containerRef.current) return;

    const observerOptions = {
      root: containerRef.current,
      rootMargin: '200px 0px', // Pre-load pages 200px before they come into view
      threshold: 0
    };

    const observer = new IntersectionObserver((entries) => {
      const newVisiblePages = new Set();
      let mostVisiblePage = pageNumber;
      let maxVisibleHeight = 0;

      // First pass: collect all visible pages
      entries.forEach(entry => {
        const pageNum = Number.parseInt(entry.target.dataset.page, 10);
        
        if (entry.isIntersecting) {
          newVisiblePages.add(pageNum);
          // Add adjacent pages for smooth scrolling
          if (pageNum > 1) newVisiblePages.add(pageNum - 1);
          if (pageNum < numPages) newVisiblePages.add(pageNum + 1);
          
          // Find the most visible page
          const visibleHeight = entry.intersectionRect.height;
          if (visibleHeight > maxVisibleHeight) {
            maxVisibleHeight = visibleHeight;
            mostVisiblePage = pageNum;
          }
        }
      });

      // Update visible pages if there are changes
      if (newVisiblePages.size > 0) {
        setVisiblePages(prev => {
          // Keep existing visible pages and add new ones
          const combined = new Set([...prev, ...newVisiblePages]);
          
          // Remove pages that are too far away (more than 3 pages)
          const filtered = new Set();
          combined.forEach(page => {
            const isNearVisible = [...newVisiblePages].some(
              visiblePage => Math.abs(page - visiblePage) <= 3
            );
            if (isNearVisible) {
              filtered.add(page);
            }
          });
          
          return filtered;
        });
      }

      // Update current page number
      if (mostVisiblePage !== pageNumber) {
        setPageNumber(mostVisiblePage);
        if (onPageChange) {
          onPageChange(mostVisiblePage);
        }
      }
    }, observerOptions);

    // Wait for next frame to ensure DOM is ready
    requestAnimationFrame(() => {
      const pageElements = containerRef.current?.querySelectorAll('.pdf-page-wrapper');
      if (pageElements) {
        pageElements.forEach(el => observer.observe(el));
      }
    });

    return () => {
      observer.disconnect();
    };
  }, [numPages, onPageChange]); // Remove pageNumber from deps to avoid re-creating observer

  const goToPrevPage = useCallback(() => {
    const newPage = Math.max(pageNumber - 1, 1);
    scrollToPage(newPage);
  }, [pageNumber, scrollToPage]);

  const goToNextPage = useCallback(() => {
    const newPage = Math.min(pageNumber + 1, numPages);
    scrollToPage(newPage);
  }, [pageNumber, numPages, scrollToPage]);

  const handleSliderChange = useCallback((e) => {
    const newPage = Number.parseInt(e.target.value, 10);
    scrollToPage(newPage);
  }, [scrollToPage]);

  return (
    <div className="pdf-viewer-container">
      <div className="pdf-viewer-wrapper" ref={containerRef}>
        <div 
          ref={documentRef}
          style={{
            transform: `scale(${scale})`,
            transformOrigin: 'center top',
            transition: 'transform 0.2s ease-out',
            width: 'max-content',
            margin: '0 auto'
          }}
        >
          <Document
            file={url}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={<div className="pdf-loading">Loading PDF...</div>}
            error={<div className="pdf-error">Failed to load PDF</div>}
            className="pdf-document"
            options={documentOptions}
          >
          {numPages && Array.from({ length: numPages }, (_, i) => i + 1).map(pageNum => (
            <div 
              key={pageNum} 
              ref={el => pagesRef.current[pageNum] = el}
              className="pdf-page-wrapper"
              data-page={pageNum}
            >
              {visiblePages.has(pageNum) ? (
                <Page
                  pageNumber={pageNum}
                  className="pdf-page"
                  renderTextLayer={true}
                  renderAnnotationLayer={false}
                  loading={
                    <div className="pdf-page-placeholder">
                      <div className="pdf-page-spinner">Loading page {pageNum}...</div>
                    </div>
                  }
                />
              ) : (
                <div className="pdf-page-placeholder">
                  <div className="pdf-page-number">Page {pageNum}</div>
                </div>
              )}
            </div>
          ))}
          </Document>
        </div>
      </div>
    </div>
  );
});

PDFViewer.displayName = 'PDFViewer';

export default PDFViewer;
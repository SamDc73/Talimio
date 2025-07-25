"""Video transcript chunker with timestamp preservation."""

import logging
from dataclasses import dataclass
from typing import Any

import tiktoken


logger = logging.getLogger(__name__)


@dataclass
class VideoChunk:
    """Represents a chunk of video transcript with timing metadata."""

    text: str
    start_time: float
    end_time: float
    chunk_index: int
    total_chunks: int
    metadata: dict[str, Any]


class VideoTranscriptChunker:
    """Chunks video transcripts while preserving timestamp information."""

    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 50,
        target_duration_seconds: int = 180,  # 3 minutes default
    ) -> None:
        """Initialize the video transcript chunker.

        Args:
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Number of tokens to overlap between chunks
            target_duration_seconds: Target duration for each chunk in seconds
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.target_duration = target_duration_seconds
        self.encoder = tiktoken.encoding_for_model("text-embedding-3-small")

    def chunk_transcript(
        self,
        segments: list[dict[str, Any]],
        video_duration: int,
        video_id: str,
    ) -> list[VideoChunk]:
        """Chunk transcript segments based on video duration and content.

        Args:
            segments: List of transcript segments with start/end times and text
            video_duration: Total video duration in seconds
            video_id: Video identifier for metadata

        Returns
        -------
            List of VideoChunk objects
        """
        if not segments:
            return []

        # Get settings for thresholds
        from src.config.settings import get_settings
        settings = get_settings()

        # Determine chunking strategy based on video duration
        if video_duration < settings.RAG_VIDEO_SHORT_DURATION_THRESHOLD:  # < 10 minutes
            return self._create_single_chunk(segments, video_duration, video_id)
        if video_duration < settings.RAG_VIDEO_MEDIUM_DURATION_THRESHOLD:  # < 30 minutes
            return self._chunk_by_time(segments, settings.RAG_VIDEO_TARGET_DURATION, video_id)  # 3-minute chunks
        # >= 30 minutes
        return self._chunk_by_time(segments, settings.RAG_VIDEO_LONG_DURATION_CHUNK, video_id)  # 5-minute chunks

    def _create_single_chunk(
        self,
        segments: list[dict[str, Any]],
        video_duration: int,
        video_id: str,
    ) -> list[VideoChunk]:
        """Create a single chunk for short videos."""
        full_text = " ".join(seg.get("text", "") for seg in segments)

        return [
            VideoChunk(
                text=full_text,
                start_time=0,
                end_time=video_duration,
                chunk_index=0,
                total_chunks=1,
                metadata={
                    "video_id": video_id,
                    "type": "full_video",
                    "segment_count": len(segments),
                },
            )
        ]

    def _chunk_by_time(
        self,
        segments: list[dict[str, Any]],
        target_seconds: int,
        video_id: str,
    ) -> list[VideoChunk]:
        """Chunk transcript by time intervals with token limits."""
        chunks = []
        current_chunk = {
            "segments": [],
            "text_parts": [],
            "start_time": 0,
            "token_count": 0,
        }

        for segment in segments:
            segment_text = segment.get("text", "").strip()
            if not segment_text:
                continue

            segment_tokens = len(self.encoder.encode(segment_text))
            segment_start = segment.get("start", 0)
            segment_end = segment.get("end", segment_start)

            # Check if adding this segment would exceed limits
            duration = segment_end - current_chunk["start_time"]
            would_exceed_tokens = (
                current_chunk["token_count"] + segment_tokens > self.max_tokens
            )
            would_exceed_time = duration > target_seconds

            # Start new chunk if limits exceeded and current chunk has content
            if current_chunk["text_parts"] and (would_exceed_tokens or would_exceed_time):
                # Finalize current chunk
                chunks.append(self._finalize_chunk(current_chunk, len(chunks)))

                # Start new chunk with overlap
                overlap_segments = self._get_overlap_segments(
                    current_chunk["segments"], self.overlap_tokens
                )

                current_chunk = {
                    "segments": overlap_segments,
                    "text_parts": [s.get("text", "") for s in overlap_segments],
                    "start_time": overlap_segments[0].get("start", segment_start) if overlap_segments else segment_start,
                    "token_count": sum(
                        len(self.encoder.encode(s.get("text", "")))
                        for s in overlap_segments
                    ),
                }

            # Add segment to current chunk
            current_chunk["segments"].append(segment)
            current_chunk["text_parts"].append(segment_text)
            current_chunk["token_count"] += segment_tokens

        # Don't forget the last chunk
        if current_chunk["text_parts"]:
            chunks.append(self._finalize_chunk(current_chunk, len(chunks)))

        # Set total chunks count
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total_chunks
            chunk.metadata["video_id"] = video_id

        return chunks

    def _get_overlap_segments(
        self, segments: list[dict[str, Any]], target_overlap_tokens: int
    ) -> list[dict[str, Any]]:
        """Get segments from the end to create overlap."""
        if not segments or target_overlap_tokens <= 0:
            return []

        overlap_segments = []
        token_count = 0

        # Work backwards to find segments for overlap
        for segment in reversed(segments):
            segment_tokens = len(self.encoder.encode(segment.get("text", "")))
            if token_count + segment_tokens > target_overlap_tokens:
                break
            overlap_segments.insert(0, segment)
            token_count += segment_tokens

        return overlap_segments

    def _finalize_chunk(self, chunk_data: dict, chunk_index: int) -> VideoChunk:
        """Finalize a chunk with proper metadata."""
        segments = chunk_data["segments"]

        return VideoChunk(
            text=" ".join(chunk_data["text_parts"]),
            start_time=segments[0].get("start", 0),
            end_time=segments[-1].get("end", 0),
            chunk_index=chunk_index,
            total_chunks=0,  # Will be set later
            metadata={
                "type": "time_segment",
                "segment_count": len(segments),
                "token_count": chunk_data["token_count"],
            },
        )

    def chunk_by_chapters(
        self,
        segments: list[dict[str, Any]],
        chapters: list[dict[str, Any]],
        video_id: str,
    ) -> list[VideoChunk]:
        """Chunk transcript by video chapters if available."""
        if not chapters or not segments:
            return []

        chunks = []

        for i, chapter in enumerate(chapters):
            chapter_start = chapter.get("start_time", 0)
            chapter_end = chapter.get("end_time", float("inf"))
            chapter_title = chapter.get("title", f"Chapter {i + 1}")

            # Find segments within this chapter
            chapter_segments = [
                seg for seg in segments
                if chapter_start <= seg.get("start", 0) < chapter_end
            ]

            if not chapter_segments:
                continue

            # Combine chapter segments
            chapter_text = " ".join(seg.get("text", "") for seg in chapter_segments)
            token_count = len(self.encoder.encode(chapter_text))

            # If chapter is too large, split it further
            if token_count > self.max_tokens:
                # Use target duration from settings
                from src.config.settings import get_settings
                settings = get_settings()
                sub_chunks = self._chunk_by_time(chapter_segments, settings.RAG_VIDEO_TARGET_DURATION, video_id)
                for sub_chunk in sub_chunks:
                    sub_chunk.metadata["chapter"] = chapter_title
                    sub_chunk.metadata["type"] = "chapter_segment"
                chunks.extend(sub_chunks)
            else:
                # Create single chunk for chapter
                chunks.append(
                    VideoChunk(
                        text=chapter_text,
                        start_time=chapter_start,
                        end_time=min(
                            chapter_end,
                            chapter_segments[-1].get("end", chapter_end)
                        ),
                        chunk_index=len(chunks),
                        total_chunks=0,  # Will be set later
                        metadata={
                            "video_id": video_id,
                            "type": "chapter",
                            "chapter": chapter_title,
                            "token_count": token_count,
                        },
                    )
                )

        # Update total chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total_chunks

        return chunks

"""
Video and Audio ingestor for Ariadne.

Extracts metadata, subtitles, and transcription from media files.
"""

from ariadne.ingest.base import BaseIngestor, SourceType
from typing import List, Optional, Dict
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)


class VideoIngestor(BaseIngestor):
    """
    Ingest video files.
    
    Extracts:
    - Metadata (duration, codec, resolution, etc.)
    - Embedded subtitles (SRT, VTT)
    - Audio track transcription (if Whisper available)
    - Key frame screenshots (metadata only)
    
    Requires: ffprobe (via ffmpeg) for metadata
              whisper (optional) for transcription
    
    Example:
        ingestor = VideoIngestor()
        docs = ingestor.ingest("lecture.mp4")
    """
    
    source_type = SourceType.UNKNOWN
    
    def __init__(self, extract_subtitles: bool = True, transcribe: bool = False):
        """
        Initialize video ingestor.
        
        Args:
            extract_subtitles: Extract embedded subtitles if available.
            transcribe: Run transcription (requires whisper, slow).
        """
        self.extract_subtitles = extract_subtitles
        self.transcribe = transcribe
    
    def _extract(self, path: Path) -> List[str]:
        """Extract metadata and subtitles from video."""
        blocks = []
        
        # Extract metadata
        metadata = self._get_video_metadata(path)
        if metadata:
            blocks.append(f"[Video Metadata] {json.dumps(metadata, ensure_ascii=False)}")
        
        # Extract subtitles if requested
        if self.extract_subtitles:
            subtitles = self._extract_subtitles(path)
            if subtitles:
                blocks.extend(subtitles)
        
        # Transcribe if requested
        if self.transcribe:
            transcript = self._transcribe_video(path)
            if transcript:
                chunks = self.chunk_text(transcript, max_chars=500, overlap=50)
                blocks.extend([f"[Transcript] {chunk}" for chunk in chunks])
        
        return blocks if blocks else [f"Video file: {path.name}"]
    
    def _get_video_metadata(self, path: Path) -> Optional[Dict]:
        """Extract video metadata using ffprobe."""
        import subprocess
        import json
        
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(path)
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Extract key info
                metadata = {}
                
                # Format info
                if 'format' in data:
                    fmt = data['format']
                    metadata['filename'] = fmt.get('filename', '')
                    metadata['format_name'] = fmt.get('format_name', '')
                    metadata['duration'] = fmt.get('duration', '')
                    metadata['size'] = fmt.get('size', '')
                    metadata['bit_rate'] = fmt.get('bit_rate', '')
                    metadata['tags'] = fmt.get('tags', {})
                
                # Stream info
                for stream in data.get('streams', []):
                    codec_type = stream.get('codec_type', '')
                    if codec_type == 'video':
                        metadata['video_codec'] = stream.get('codec_name', '')
                        metadata['resolution'] = f"{stream.get('width', '')}x{stream.get('height', '')}"
                        metadata['fps'] = stream.get('r_frame_rate', '')
                    elif codec_type == 'audio':
                        metadata['audio_codec'] = stream.get('codec_name', '')
                        metadata['audio_channels'] = stream.get('channels', '')
                    elif codec_type == 'subtitle':
                        if 'subtitle_codec' not in metadata:
                            metadata['subtitle_codec'] = []
                        metadata['subtitle_codec'].append(stream.get('codec_name', ''))
                
                return metadata
                
        except FileNotFoundError:
            logger.warning("ffprobe not found, skipping video metadata extraction")
        except Exception as e:
            logger.warning(f"Failed to extract video metadata: {e}")
        
        return None
    
    def _extract_subtitles(self, path: Path) -> List[str]:
        """Extract embedded subtitles."""
        import subprocess
        import tempfile
        import os
        
        subtitle_blocks = []
        
        try:
            # List subtitle streams
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-select_streams', 's', str(path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get('streams', [])
                
                for i, stream in enumerate(streams):
                    codec = stream.get('codec_name', 'unknown')
                    lang = stream.get('tags', {}).get('language', f'stream_{i}')
                    
                    # Extract as SRT
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
                            temp_path = f.name
                        
                        cmd = [
                            'ffmpeg', '-y', '-i', str(path),
                            '-map', f'0:s:{i}', temp_path
                        ]
                        
                        sub_result = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=60
                        )
                        
                        if sub_result.returncode == 0 and os.path.exists(temp_path):
                            with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                                srt_content = f.read()
                            
                            # Parse SRT and extract text
                            subtitle_text = self._parse_srt(srt_content)
                            if subtitle_text:
                                subtitle_blocks.append(
                                    f"[Subtitles ({lang})] {subtitle_text}"
                                )
                        
                        os.unlink(temp_path)
                        
                    except Exception as e:
                        logger.warning(f"Failed to extract subtitle stream {i}: {e}")
                        
        except Exception as e:
            logger.warning(f"Subtitle extraction failed: {e}")
        
        return subtitle_blocks
    
    def _parse_srt(self, srt_content: str) -> str:
        """Extract text from SRT subtitle format."""
        lines = srt_content.strip().split('\n')
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip sequence numbers and timestamps
            if line.isdigit():
                continue
            if '-->' in line:
                continue
            # Keep text
            if line:
                text_lines.append(line)
        
        return ' '.join(text_lines)
    
    def _transcribe_video(self, path: Path) -> Optional[str]:
        """Transcribe video audio using Whisper."""
        try:
            import whisper
        except ImportError:
            logger.warning("Whisper not installed, skipping transcription. "
                          "Install with: pip install openai-whisper")
            return None
        
        try:
            model = whisper.load_model("base")
            result = model.transcribe(str(path))
            return result.get('text', '')
        except Exception as e:
            logger.warning(f"Transcription failed: {e}")
            return None


class AudioIngestor(BaseIngestor):
    """
    Ingest audio files (music, podcasts, voice recordings).
    
    Extracts:
    - Metadata (artist, album, duration, etc.)
    - ID3 tags
    - Audio transcription (if Whisper available)
    
    Requires: ffprobe for metadata
              whisper (optional) for transcription
    
    Example:
        ingestor = AudioIngestor()
        docs = ingestor.ingest("podcast.mp3")
    """
    
    source_type = SourceType.UNKNOWN
    
    def __init__(self, transcribe: bool = False):
        """
        Initialize audio ingestor.
        
        Args:
            transcribe: Run transcription (requires whisper).
        """
        self.transcribe = transcribe
    
    def _extract(self, path: Path) -> List[str]:
        """Extract metadata and transcription from audio."""
        blocks = []
        
        # Extract metadata
        metadata = self._get_audio_metadata(path)
        if metadata:
            blocks.append(f"[Audio Metadata] {json.dumps(metadata, ensure_ascii=False)}")
        
        # Transcribe if requested
        if self.transcribe:
            transcript = self._transcribe_audio(path)
            if transcript:
                chunks = self.chunk_text(transcript, max_chars=500, overlap=50)
                blocks.extend([f"[Transcript] {chunk}" for chunk in chunks])
        
        return blocks if blocks else [f"Audio file: {path.name}"]
    
    def _get_audio_metadata(self, path: Path) -> Optional[Dict]:
        """Extract audio metadata using ffprobe."""
        import subprocess
        import json
        
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(path)
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                metadata = {}
                
                # Format info
                if 'format' in data:
                    fmt = data['format']
                    metadata['duration'] = fmt.get('duration', '')
                    metadata['size'] = fmt.get('size', '')
                    metadata['bit_rate'] = fmt.get('bit_rate', '')
                    metadata['tags'] = fmt.get('tags', {})
                
                # Audio stream info
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'audio':
                        metadata['codec'] = stream.get('codec_name', '')
                        metadata['channels'] = stream.get('channels', '')
                        metadata['sample_rate'] = stream.get('sample_rate', '')
                        break
                
                return metadata
                
        except FileNotFoundError:
            logger.warning("ffprobe not found, skipping audio metadata")
        except Exception as e:
            logger.warning(f"Failed to extract audio metadata: {e}")
        
        return None
    
    def _transcribe_audio(self, path: Path) -> Optional[str]:
        """Transcribe audio using Whisper."""
        try:
            import whisper
        except ImportError:
            logger.warning("Whisper not installed, skipping transcription")
            return None
        
        try:
            model = whisper.load_model("base")
            result = model.transcribe(str(path))
            return result.get('text', '')
        except Exception as e:
            logger.warning(f"Audio transcription failed: {e}")
            return None

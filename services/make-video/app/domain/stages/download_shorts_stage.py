"""
DownloadShortsStage - Download and validate shorts with OCR detection

🎯 Responsibilities:
    - Check cache for existing shorts
    - Download missing shorts
    - Validate with OCR (reject embedded subtitles)
    - Handle blacklist
    - Retry logic with multiple rounds
"""

from pathlib import Path
from typing import Dict, Any, List
import logging
import asyncio

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode


logger = logging.getLogger(__name__)


class DownloadShortsStage(JobStage):
    """Stage 3: Download and validate shorts"""
    
    def __init__(self, api_client, shorts_cache, video_validator, blacklist):
        """
        Initialize stage
        
        Args:
            api_client: APIClient for download operations
            shorts_cache: ShortsCache for caching
            video_validator: VideoValidator for OCR validation
            blacklist: Blacklist for rejected videos
        """
        super().__init__(
            name="download_shorts",
            progress_start=25.0,
            progress_end=70.0
        )
        self.api_client = api_client
        self.shorts_cache = shorts_cache
        self.video_validator = video_validator
        self.blacklist = blacklist
    
    def validate(self, context: StageContext):
        """Validate shorts list exists"""
        if not context.shorts_list:
            raise VideoProcessingException(
                "No shorts list available",
                error_code=ErrorCode.NO_SHORTS_FOUND,
                job_id=context.job_id,
            )
    
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Download shorts with cache checking and OCR validation
        
        Returns:
            Dict with downloaded_shorts, cache_hits, downloads, failures
        """
        logger.info(f"⬇️  Downloading shorts (target: {context.target_video_duration:.1f}s)")
        
        downloaded_shorts = []
        failed_downloads = []
        cache_hits = 0
        downloads = 0
        processed_ids = set()
        
        max_rounds = context.settings.get('max_fetch_rounds', 3)
        base_request = max(context.max_shorts, 10)
        
        shorts_list = context.shorts_list.copy()
        
        for round_idx in range(1, max_rounds + 1):
            logger.info(f"📦 Round {round_idx}/{max_rounds}")
            
            to_download = []
            
            # Check cache first
            for short in shorts_list:
                video_id = short['video_id']
                
                if video_id in processed_ids:
                    continue
                processed_ids.add(video_id)
                
                # Check blacklist
                if self.blacklist.is_blacklisted(video_id):
                    logger.warning(f"🚫 BLACKLIST: {video_id} - skipping")
                    failed_downloads.append(video_id)
                    continue
                
                # Check cache
                cached = self.shorts_cache.get(video_id)
                if cached:
                    try:
                        file_path = Path(cached['file_path'])
                        logger.debug(f"💾 Cache hit: {video_id}, validating...")
                        
                        # Validate integrity
                        self.video_validator.validate_video_integrity(str(file_path), timeout=5)
                        
                        # Check for embedded subtitles
                        has_subs, confidence, reason = self.video_validator.has_embedded_subtitles(str(file_path))
                        if has_subs:
                            logger.warning(
                                f"🚫 EMBEDDED SUBTITLES (cache): {video_id} (conf: {confidence:.2f})"
                            )
                            self.blacklist.add(video_id, reason, confidence, metadata={
                                'title': short.get('title', ''),
                                'duration': short.get('duration_seconds', 0)
                            })
                            self.shorts_cache.remove(video_id)
                            continue
                        
                        # Valid cached video
                        self.shorts_cache.mark_validated(video_id, False, confidence)
                        downloaded_shorts.append(cached)
                        cache_hits += 1
                        logger.info(f"✅ Cache HIT: {video_id} (conf={confidence:.2f})")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Cache invalid: {video_id} - {e}. Re-downloading.")
                        self.shorts_cache.remove(video_id)
                        to_download.append(short)
                else:
                    to_download.append(short)
            
            logger.info(f"💾 Cache: {cache_hits} hits, {len(to_download)} need download")
            
            # Download missing videos
            if len(downloaded_shorts) < min(10, base_request) and to_download:
                logger.info(f"⬇️  Downloading {len(to_download)} videos...")
                
                batch_size = 5
                for i in range(0, len(to_download), batch_size):
                    batch = to_download[i:i+batch_size]
                    tasks = [self._download_with_retry(short, context) for short in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for result in results:
                        if result and not isinstance(result, Exception):
                            downloaded_shorts.append(result)
                            downloads += 1
                        elif isinstance(result, Exception):
                            logger.debug(f"Download failed: {result}")
                    
                    # Update progress
                    if to_download:
                        progress = 30.0 + (40.0 * min(i + batch_size, len(to_download)) / len(to_download))
                    else:
                        progress = 70.0
                    
                    await context.publish_event(
                        context.event_publisher._event_type if context.event_publisher else None,
                        {'progress': progress}
                    )
            
            # Check if we have enough duration
            total_duration = sum(s.get('duration_seconds', 0) for s in downloaded_shorts)
            logger.info(
                f"📦 Round {round_idx} done: {len(downloaded_shorts)} videos, "
                f"duration {total_duration:.1f}s / target {context.target_video_duration:.1f}s"
            )
            
            if total_duration >= context.target_video_duration:
                logger.info("✅ Sufficient duration reached")
                break
            elif round_idx == max_rounds:
                raise VideoProcessingException(
                    f"Insufficient shorts after {max_rounds} rounds",
                    error_code=ErrorCode.INSUFFICIENT_DURATION,
                    details={
                        'got_duration': total_duration,
                        'target_duration': context.target_video_duration,
                        'videos_count': len(downloaded_shorts)
                    },
                    job_id=context.job_id,
                )
            else:
                logger.warning(
                    f"⚠️ Insufficient duration ({total_duration:.1f}/{context.target_video_duration:.1f}s). "
                    f"Starting round {round_idx + 1}..."
                )
        
        if not downloaded_shorts:
            raise VideoProcessingException(
                "No shorts could be downloaded",
                error_code=ErrorCode.NO_VALID_SHORTS,
                job_id=context.job_id,
            )
        
        logger.info(
            f"📦 Download complete: {len(downloaded_shorts)} videos "
            f"({cache_hits} cache hits, {downloads} downloads, {len(failed_downloads)} failures)"
        )
        
        # Update context
        context.downloaded_shorts = downloaded_shorts
        
        return {
            'downloaded_count': len(downloaded_shorts),
            'cache_hits': cache_hits,
            'downloads': downloads,
            'failures': len(failed_downloads),
            'total_duration': sum(s.get('duration_seconds', 0) for s in downloaded_shorts),
        }
    
    async def _download_with_retry(self, short_info: Dict, context: StageContext) -> Dict[str, Any]:
        """Download single video with retry logic"""
        video_id = short_info['video_id']
        output_path = Path(context.settings['shorts_cache_dir']) / f"{video_id}.mp4"
        
        # Check blacklist before download
        if self.blacklist.is_blacklisted(video_id):
            logger.warning(f"🚫 BLACKLIST: {video_id}")
            return None
        
        for attempt in range(3):
            try:
                # Download video
                await self.api_client.download_short(video_id, str(output_path))
                
                # Validate integrity
                self.video_validator.validate_video_integrity(str(output_path), timeout=10)
                
                # Check for embedded subtitles
                has_subs, confidence, reason = self.video_validator.has_embedded_subtitles(str(output_path))
                
                if has_subs:
                    logger.warning(f"🚫 EMBEDDED SUBTITLES: {video_id} (conf: {confidence:.2f})")
                    self.blacklist.add(video_id, reason, confidence, metadata=short_info)
                    if output_path.exists():
                        output_path.unlink()
                    return None
                
                # Valid video - cache it
                short_data = {
                    **short_info,
                    'file_path': str(output_path),
                    'has_embedded_subtitles': False,
                    'ocr_confidence': confidence,
                }
                
                self.shorts_cache.add(video_id, short_data)
                self.shorts_cache.mark_validated(video_id, False, confidence)
                
                logger.info(f"✅ Downloaded: {video_id} (conf={confidence:.2f})")
                return short_data
                
            except Exception as e:
                logger.warning(f"⚠️ Download attempt {attempt+1}/3 failed for {video_id}: {e}")
                if attempt == 2:
                    logger.error(f"❌ Download failed after 3 attempts: {video_id}")
                    return None
                await asyncio.sleep(1 * (attempt + 1))
        
        return None

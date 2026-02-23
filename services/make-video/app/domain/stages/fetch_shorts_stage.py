"""
FetchShortsStage - Search for YouTube shorts matching query

🎯 Responsibilities:
    - Call YouTube search API
    - Retrieve list of shorts
    - Validate results
"""

from typing import Dict, Any
import logging

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode


logger = logging.getLogger(__name__)


class FetchShortsStage(JobStage):
    """Stage 2: Fetch shorts from YouTube API"""
    
    def __init__(self, api_client):
        """
        Initialize stage
        
        Args:
            api_client: APIClient instance for YouTube operations
        """
        super().__init__(
            name="fetch_shorts",
            progress_start=15.0,
            progress_end=25.0
        )
        self.api_client = api_client
    
    def validate(self, context: StageContext):
        """Validate query is present"""
        if not context.query or not context.query.strip():
            raise VideoProcessingException(
                "Query is empty",
                error_code=ErrorCode.INVALID_QUERY,
                details={'query': context.query},
                job_id=context.job_id,
            )
    
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Fetch shorts from YouTube
        
        Returns:
            Dict with shorts_list and count
        """
        logger.info(f"🔍 Fetching shorts for query: '{context.query}' (max: {context.max_shorts})")
        
        shorts_list = await self.api_client.search_shorts(
            context.query,
            context.max_shorts
        )
        
        logger.info(f"✅ Found {len(shorts_list)} shorts")
        
        if not shorts_list:
            raise VideoProcessingException(
                f"No shorts found for query: {context.query}",
                error_code=ErrorCode.NO_SHORTS_FOUND,
                details={
                    'query': context.query,
                    'max_shorts': context.max_shorts
                },
                job_id=context.job_id,
            )
        
        # Update context
        context.shorts_list = shorts_list
        
        return {
            'shorts_count': len(shorts_list),
            'query': context.query,
        }

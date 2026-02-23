"""
Subprocess Utilities with Timeout Support

Provides safe subprocess execution with automatic timeout and cleanup.
Prevents FFmpeg and other processes from hanging indefinitely.
"""
import asyncio
import logging
import signal
import subprocess
from typing import List, Optional, Tuple
from pathlib import Path

# Use new exception hierarchy
from ..shared.exceptions_v2 import (
    SubprocessTimeoutException,
    FFmpegTimeoutException,
    FFprobeFailedException
)

logger = logging.getLogger(__name__)

# Default timeout values (seconds) - following Netflix/Google standards
DEFAULT_SUBPROCESS_TIMEOUT = 300  # 5 minutes for generic subprocess
DEFAULT_FFMPEG_TIMEOUT = 600      # 10 minutes for FFmpeg operations
DEFAULT_FFPROBE_TIMEOUT = 30      # 30 seconds for metadata extraction
SIGTERM_GRACE_PERIOD = 2          # Grace period before SIGKILL


async def run_subprocess_with_timeout(
    cmd: List[str],
    timeout: int = DEFAULT_SUBPROCESS_TIMEOUT,
    check: bool = True,
    capture_output: bool = True
) -> Tuple[int, bytes, bytes]:
    """
    Run subprocess with timeout protection
    
    Args:
        cmd: Command and arguments
        timeout: Maximum execution time in seconds (default: 300s = 5min)
        check: Raise exception on non-zero exit code
        capture_output: Capture stdout/stderr
    
    Returns:
        Tuple of (returncode, stdout, stderr)
    
    Raises:
        SubprocessTimeoutException: If process exceeds timeout
        subprocess.CalledProcessError: If check=True and returncode != 0
    """
    cmd_str = ' '.join(cmd[:3]) + ('...' if len(cmd) > 3 else '')
    logger.debug(f"Running subprocess: {cmd_str} (timeout: {timeout}s)")
    
    process = None
    
    try:
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None
        )
        
        logger.debug(f"Subprocess started: PID {process.pid}")
        
        # Wait with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            returncode = process.returncode
            
            if returncode != 0:
                logger.warning(
                    f"Subprocess failed: {cmd_str} (exit code: {returncode})"
                )
                
                if check:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    raise subprocess.CalledProcessError(
                        returncode, cmd, stdout, stderr
                    )
            else:
                logger.debug(f"Subprocess completed: {cmd_str}")
            
            return returncode, stdout or b'', stderr or b''
        
        except asyncio.TimeoutError:
            # Timeout! Kill process
            logger.error(
                f"⚠️ Subprocess TIMEOUT after {timeout}s: {cmd_str} (PID: {process.pid})"
            )
            
            # Try graceful termination first
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
                logger.info(f"Process terminated gracefully: PID {process.pid}")
            except asyncio.TimeoutError:
                # Force kill
                logger.warning(f"Force killing process: PID {process.pid}")
                process.kill()
                await process.wait()
            
            raise SubprocessTimeoutException(
                command=cmd_str,
                timeout=timeout,
                pid=process.pid
            )
    
    except Exception as e:
        if process and process.returncode is None:
            # Process still running, kill it
            try:
                process.kill()
                await process.wait()
            except:
                pass
        
        raise


def run_subprocess_sync_with_timeout(
    cmd: List[str],
    timeout: int = 300,
    check: bool = True,
    capture_output: bool = True
) -> subprocess.CompletedProcess:
    """
    Synchronous version of run_subprocess_with_timeout
    
    For use in non-async code.
    
    Args:
        cmd: Command and arguments
        timeout: Maximum execution time in seconds
        check: Raise exception on non-zero exit code
        capture_output: Capture stdout/stderr
    
    Returns:
        CompletedProcess instance
    
    Raises:
        subprocess.TimeoutExpired: If process exceeds timeout
        subprocess.CalledProcessError: If check=True and returncode != 0
    """
    cmd_str = ' '.join(cmd[:3]) + ('...' if len(cmd) > 3 else '')
    logger.debug(f"Running subprocess (sync): {cmd_str} (timeout: {timeout}s)")
    
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            check=check,
            capture_output=capture_output,
            text=False
        )
        
        logger.debug(f"Subprocess completed (sync): {cmd_str}")
        return result
    
    except subprocess.TimeoutExpired as e:
        logger.error(f"⚠️ Subprocess TIMEOUT (sync) after {timeout}s: {cmd_str}")
        raise
    
    except subprocess.CalledProcessError as e:
        logger.warning(f"Subprocess failed (sync): {cmd_str} (exit code: {e.returncode})")
        raise


async def run_ffmpeg_with_timeout(
    args: List[str],
    timeout: int = 600,
    input_file: Optional[str] = None,
    output_file: Optional[str] = None
) -> Tuple[int, bytes, bytes]:
    """
    Run FFmpeg command with appropriate timeout
    
    Wrapper around run_subprocess_with_timeout with FFmpeg-specific defaults.
    
    Args:
        args: FFmpeg arguments (without 'ffmpeg' command)
        timeout: Maximum execution time (default: 600s = 10min)
        input_file: Input file path (for logging)
        output_file: Output file path (for logging)
    
    Returns:
        Tuple of (returncode, stdout, stderr)
    
    Raises:
        SubprocessTimeoutException: If FFmpeg exceeds timeout
    """
    cmd = ['ffmpeg', '-y'] + args  # -y to overwrite output files
    
    # Enhanced logging
    if input_file and output_file:
        logger.info(
            f"🎬 FFmpeg: {Path(input_file).name} → {Path(output_file).name}",
            extra={
                'operation': 'ffmpeg',
                'input_file': input_file,
                'output_file': output_file,
                'timeout': timeout
            }
        )
    
    return await run_subprocess_with_timeout(
        cmd=cmd,
        timeout=timeout,
        check=True,
        capture_output=True
    )


async def run_ffprobe(
    file_path: str,
    args: List[str] = None,
    timeout: int = DEFAULT_FFPROBE_TIMEOUT
) -> str:
    """
    Run ffprobe to extract video/audio metadata
    
    Args:
        file_path: Path to media file
        args: Additional ffprobe arguments
        timeout: Maximum execution time (default: 30s)
    
    Returns:
        ffprobe output as string
    
    Raises:
        SubprocessTimeoutException: If ffprobe exceeds timeout
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-print_format', 'json',
        '-show_format',
        '-show_streams'
    ]
    
    if args:
        cmd.extend(args)
    
    cmd.append(file_path)
    
    returncode, stdout, stderr = await run_subprocess_with_timeout(
        cmd=cmd,
        timeout=timeout,
        check=True,
        capture_output=True
    )
    
    return stdout.decode('utf-8')


async def kill_process_tree(pid: int, timeout: int = 5):
    """
    Kill process and all its children
    
    Args:
        pid: Process ID to kill
        timeout: Maximum time to wait for termination
    """
    try:
        # Get all child processes
        import psutil
        
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        logger.info(f"Killing process tree: PID {pid} + {len(children)} children")
        
        # Terminate children first
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        # Terminate parent
        parent.terminate()
        
        # Wait for termination
        _, alive = psutil.wait_procs(
            children + [parent],
            timeout=timeout
        )
        
        # Force kill survivors
        for process in alive:
            try:
                logger.warning(f"Force killing: PID {process.pid}")
                process.kill()
            except psutil.NoSuchProcess:
                pass
        
        logger.info(f"✅ Process tree killed: PID {pid}")
    
    except ImportError:
        # psutil not available, fallback to simple kill
        logger.warning("psutil not available, using simple kill")
        
        try:
            import os
            os.kill(pid, signal.SIGTERM)
            
            # Wait a bit
            await asyncio.sleep(1)
            
            # Force kill if still alive
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Already dead
        
        except ProcessLookupError:
            pass  # Process already dead
    
    except Exception as e:
        logger.error(f"Failed to kill process tree: {e}")
        raise

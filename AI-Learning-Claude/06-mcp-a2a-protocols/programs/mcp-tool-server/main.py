# MCP Tool Server - Practical file system and API tools
#
# Demonstrates real-world MCP tool patterns:
# - File system operations with security
# - Simulated API integration
# - Input validation
# - Error handling

import os
import glob as glob_module
import logging
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP("mcp-tool-server")

# Security: restrict file access to this directory (default: current working dir)
ALLOWED_ROOT = os.getenv("ALLOWED_ROOT", os.getcwd())
MAX_FILE_SIZE = 1_000_000  # 1MB max file read


def _safe_path(path: str) -> str:
    """Resolve path and ensure it's within the allowed root directory.
    Prevents path traversal attacks (e.g., ../../etc/passwd).
    """
    resolved = os.path.realpath(os.path.join(ALLOWED_ROOT, path))
    if not resolved.startswith(os.path.realpath(ALLOWED_ROOT)):
        raise ValueError(f"Access denied: path is outside allowed directory")
    return resolved


# =============================================================================
# TOOLS
# =============================================================================

@mcp.tool()
def search_files(pattern: str, directory: str = ".") -> str:
    """Search for files matching a glob pattern within the allowed directory.
    
    Args:
        pattern: Glob pattern to match (e.g., '*.py', '**/*.md', 'src/*.ts')
        directory: Subdirectory to search in (relative to root). Default is root.
    
    Returns:
        List of matching file paths, one per line. Returns 'No matches found' if empty.
    """
    logger.info(f"Tool: search_files(pattern={pattern}, directory={directory})")
    
    # Validate pattern isn't too broad
    if pattern in ("*", "**", "**/*"):
        raise ValueError("Pattern too broad. Please be more specific (e.g., '*.py')")
    
    safe_dir = _safe_path(directory)
    
    if not os.path.isdir(safe_dir):
        raise ValueError(f"Directory not found: {directory}")
    
    search_pattern = os.path.join(safe_dir, pattern)
    matches = glob_module.glob(search_pattern, recursive=True)
    
    # Limit results
    if len(matches) > 100:
        matches = matches[:100]
        suffix = "\n... (truncated, showing first 100 results)"
    else:
        suffix = ""
    
    if not matches:
        return "No matches found"
    
    # Return relative paths for readability
    relative = [os.path.relpath(m, ALLOWED_ROOT) for m in matches]
    return "\n".join(sorted(relative)) + suffix


@mcp.tool()
def read_file(path: str, max_lines: int = 200) -> str:
    """Read the contents of a text file.
    
    Args:
        path: File path relative to the allowed root directory
        max_lines: Maximum number of lines to read (default 200, max 1000)
    
    Returns:
        The file contents as text. Binary files will return an error.
    """
    logger.info(f"Tool: read_file(path={path}, max_lines={max_lines})")
    
    max_lines = min(max_lines, 1000)
    safe_path = _safe_path(path)
    
    if not os.path.exists(safe_path):
        raise ValueError(f"File not found: {path}")
    
    if not os.path.isfile(safe_path):
        raise ValueError(f"Not a file: {path}")
    
    file_size = os.path.getsize(safe_path)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large ({file_size} bytes). Maximum is {MAX_FILE_SIZE} bytes.")
    
    try:
        with open(safe_path, "r", encoding="utf-8") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"\n... (truncated at {max_lines} lines)")
                    break
                lines.append(line)
        return "".join(lines)
    except UnicodeDecodeError:
        raise ValueError(f"Cannot read binary file: {path}")


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and subdirectories in a directory.
    
    Args:
        path: Directory path relative to root. Use '.' for the root directory.
    
    Returns:
        Listing of directory contents with type indicators (/ for directories).
    """
    logger.info(f"Tool: list_directory(path={path})")
    
    safe_path = _safe_path(path)
    
    if not os.path.isdir(safe_path):
        raise ValueError(f"Not a directory: {path}")
    
    entries = []
    try:
        for entry in sorted(os.listdir(safe_path)):
            full = os.path.join(safe_path, entry)
            if os.path.isdir(full):
                entries.append(f"{entry}/")
            else:
                size = os.path.getsize(full)
                entries.append(f"{entry} ({size} bytes)")
    except PermissionError:
        raise ValueError(f"Permission denied: {path}")
    
    if not entries:
        return "(empty directory)"
    
    return "\n".join(entries)


@mcp.tool()
def get_weather(city: str) -> str:
    """Get current weather for a city (simulated - returns mock data).
    
    In a real implementation, this would call a weather API.
    Demonstrates how to integrate external APIs as MCP tools.
    
    Args:
        city: City name (e.g., 'London', 'New York', 'Tokyo')
    
    Returns:
        Weather information including temperature, conditions, and humidity.
    """
    logger.info(f"Tool: get_weather(city={city})")
    
    if not city or len(city) > 100:
        raise ValueError("City name must be 1-100 characters")
    
    # Simulated weather data (in production, call a real API)
    import hashlib
    # Generate deterministic but varied data based on city name
    hash_val = int(hashlib.md5(city.lower().encode()).hexdigest()[:8], 16)
    temp = 5 + (hash_val % 30)  # 5-35°C
    humidity = 30 + (hash_val % 60)  # 30-90%
    conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Overcast"]
    condition = conditions[hash_val % len(conditions)]
    
    return (
        f"Weather for {city}:\n"
        f"  Temperature: {temp}°C\n"
        f"  Condition: {condition}\n"
        f"  Humidity: {humidity}%\n"
        f"  (Note: This is simulated data for demonstration)"
    )


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    logger.info("Starting MCP Tool Server...")
    logger.info(f"Allowed root directory: {ALLOWED_ROOT}")
    logger.info("Tools: search_files, read_file, list_directory, get_weather")
    mcp.run()

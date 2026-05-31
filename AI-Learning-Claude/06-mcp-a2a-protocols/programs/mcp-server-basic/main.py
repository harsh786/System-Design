# MCP Server Basic - Demonstrates Tools, Resources, and Prompts
# 
# This server exposes:
# - 2 Tools: get_current_time, calculate_sum
# - 1 Resource: system_info
# - 1 Prompt: greeting_prompt

import platform
import sys
import logging
from datetime import datetime

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Create the MCP server instance
# "mcp-server-basic" is the server name that clients will see
mcp = FastMCP("mcp-server-basic")


# =============================================================================
# TOOLS - Functions the AI can call to perform actions
# =============================================================================

@mcp.tool()
def get_current_time(timezone: str = "UTC") -> str:
    """Get the current date and time.
    
    Args:
        timezone: Timezone name (currently only UTC supported for simplicity)
    
    Returns:
        Current date and time as a formatted string
    """
    logger.info(f"Tool called: get_current_time(timezone={timezone})")
    now = datetime.utcnow()
    result = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info(f"Tool result: {result}")
    return result


@mcp.tool()
def calculate_sum(numbers: list[float]) -> float:
    """Calculate the sum of a list of numbers.
    
    Args:
        numbers: A list of numbers to add together
    
    Returns:
        The sum of all numbers
    """
    logger.info(f"Tool called: calculate_sum(numbers={numbers})")
    
    if not numbers:
        raise ValueError("Cannot sum an empty list")
    
    if len(numbers) > 1000:
        raise ValueError("Too many numbers (max 1000)")
    
    result = sum(numbers)
    logger.info(f"Tool result: {result}")
    return result


# =============================================================================
# RESOURCES - Data the AI can read (like files or database records)
# =============================================================================

@mcp.resource("system://info")
def system_info() -> str:
    """System information including OS, Python version, and architecture."""
    logger.info("Resource accessed: system://info")
    
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": sys.version,
        "hostname": platform.node(),
    }
    
    # Format as readable text
    lines = [f"{key}: {value}" for key, value in info.items()]
    return "\n".join(lines)


# =============================================================================
# PROMPTS - Pre-built prompt templates that guide AI behavior
# =============================================================================

@mcp.prompt()
def greeting_prompt(name: str, style: str = "friendly") -> str:
    """Generate a personalized greeting.
    
    Args:
        name: The person's name to greet
        style: Greeting style - 'friendly', 'formal', or 'casual'
    """
    logger.info(f"Prompt requested: greeting(name={name}, style={style})")
    
    if style == "formal":
        return f"Please compose a formal, professional greeting for {name}. Be respectful and use proper titles if appropriate."
    elif style == "casual":
        return f"Write a casual, relaxed greeting for {name}. Keep it short and fun."
    else:
        return f"Write a warm, friendly greeting for {name}. Be welcoming and positive."


# =============================================================================
# MAIN - Server entry point
# =============================================================================

if __name__ == "__main__":
    logger.info("Starting MCP Server Basic...")
    logger.info("Capabilities: 2 tools, 1 resource, 1 prompt")
    logger.info("Transport: stdio")
    
    # Run the server using stdio transport (default)
    # The server will listen on stdin and write to stdout
    mcp.run()

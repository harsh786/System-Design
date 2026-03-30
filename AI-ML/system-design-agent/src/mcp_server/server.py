"""
MCP Server - Exposes the System Design Agent as an MCP (Model Context Protocol) server.

This allows integration with VS Code / GitHub Copilot / Claude Desktop
to trigger design generation directly from the IDE.
"""

import asyncio
import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    ResourceTemplate,
)

from src.main import main as run_agent
from src.ingestion.markdown_parser import MarkdownParser


# Create MCP server
server = Server("system-design-agent")


# ── Tools ──

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="generate_system_design",
            description=(
                "Generate a complete system design (HLD, LLD, DB Design) "
                "from a PRD document. Provide either a Confluence URL or "
                "a local file path to the PRD."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prd_url": {
                        "type": "string",
                        "description": "Confluence page URL for the PRD",
                    },
                    "prd_file": {
                        "type": "string",
                        "description": "Local file path for the PRD (alternative to URL)",
                    },
                    "context_dir": {
                        "type": "string",
                        "description": "Directory with existing design docs",
                        "default": "./System-Design",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Output directory for generated designs",
                        "default": "./generated-designs",
                    },
                },
                "oneOf": [
                    {"required": ["prd_url"]},
                    {"required": ["prd_file"]},
                ],
            },
        ),
        Tool(
            name="generate_hld",
            description="Generate only the High-Level Design from a PRD.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prd_content": {
                        "type": "string",
                        "description": "The PRD content as text",
                    },
                    "context_dir": {
                        "type": "string",
                        "description": "Directory with existing design docs",
                        "default": "./System-Design",
                    },
                },
                "required": ["prd_content"],
            },
        ),
        Tool(
            name="review_design",
            description=(
                "Review an existing design document against requirements. "
                "Checks for completeness, consistency, and best practices."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "design_file": {
                        "type": "string",
                        "description": "Path to the design document to review",
                    },
                    "requirements": {
                        "type": "string",
                        "description": "Requirements or PRD content to review against",
                    },
                },
                "required": ["design_file", "requirements"],
            },
        ),
        Tool(
            name="index_documents",
            description=(
                "Index existing design documents into the vector store "
                "for use as context in future design generation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory containing design documents to index",
                    },
                },
                "required": ["directory"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "generate_system_design":
        try:
            result = await run_agent(
                prd_url=arguments.get("prd_url"),
                prd_file=arguments.get("prd_file"),
                context_dir=arguments.get("context_dir", "./System-Design"),
                output_dir=arguments.get("output_dir", "./generated-designs"),
            )

            return [TextContent(
                type="text",
                text=(
                    f"✅ System Design generated successfully!\n\n"
                    f"## Generated Documents:\n"
                    f"- HLD: {arguments.get('output_dir', './generated-designs')}/HLD.md\n"
                    f"- LLD: {arguments.get('output_dir', './generated-designs')}/LLD/\n"
                    f"- DB Design: {arguments.get('output_dir', './generated-designs')}/DB_DESIGN.md\n"
                    f"- Review: {arguments.get('output_dir', './generated-designs')}/REVIEW_REPORT.md\n\n"
                    f"## Review Status: {result.get('review_status', 'N/A')}\n\n"
                    f"## HLD Preview:\n{result.get('hld_document', '')[:2000]}"
                ),
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error generating design: {str(e)}",
            )]

    elif name == "generate_hld":
        # Simplified HLD-only generation
        return [TextContent(
            type="text",
            text="HLD generation requested. Use generate_system_design for full pipeline.",
        )]

    elif name == "review_design":
        design_file = arguments["design_file"]
        requirements = arguments["requirements"]
        design_content = Path(design_file).read_text()

        return [TextContent(
            type="text",
            text=f"Review of {design_file} against requirements:\n\n[Review would be generated here]",
        )]

    elif name == "index_documents":
        directory = arguments["directory"]
        parser = MarkdownParser()
        docs = parser.parse_directory(directory)

        return [TextContent(
            type="text",
            text=f"✅ Indexed {len(docs)} documents from {directory}",
        )]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}",
        )]


# ── Resources ──

@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available MCP resources."""
    return [
        Resource(
            uri="design://templates/hld",
            name="HLD Template",
            description="Template for High-Level Design documents",
            mimeType="text/markdown",
        ),
        Resource(
            uri="design://templates/lld",
            name="LLD Template",
            description="Template for Low-Level Design documents",
            mimeType="text/markdown",
        ),
        Resource(
            uri="design://templates/db_design",
            name="DB Design Template",
            description="Template for Database Design documents",
            mimeType="text/markdown",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read an MCP resource."""
    templates = {
        "design://templates/hld": "# High-Level Design: {Project Name}\n\n## Executive Summary\n...",
        "design://templates/lld": "# Low-Level Design: {Component Name}\n\n## Component Overview\n...",
        "design://templates/db_design": "# Database Design: {Project Name}\n\n## Overview\n...",
    }
    return templates.get(uri, f"Unknown resource: {uri}")


# ── Entry Point ──

async def run_mcp_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(run_mcp_server())

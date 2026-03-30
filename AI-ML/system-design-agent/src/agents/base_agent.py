"""
Base Agent Class - Custom implementation using Claude API directly

This provides the foundation for all SDLC agents without LangChain dependency.
"""

import os
import json
from typing import Dict, Any, List, Optional
import anthropic
import structlog

logger = structlog.get_logger()


class BaseAgent:
    """
    Base class for custom agents using Claude API directly.
    
    All SDLC agents inherit from this base class.
    """
    
    def __init__(
        self,
        agent_name: str,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        """
        Initialize base agent with Claude client.
        
        Args:
            agent_name: Name of the agent for logging
            model: Claude model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        """
        self.agent_name = agent_name
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
        logger.info(
            "agent_initialized",
            agent=agent_name,
            model=model,
        )
    
    async def call_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
    ) -> str:
        """
        Call Claude API with prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            tools: Optional tool definitions for tool use
            
        Returns:
            Claude's response content
        """
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": messages,
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            if tools:
                kwargs["tools"] = tools
            
            response = self.client.messages.create(**kwargs)
            
            # Extract text content
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text
            
            logger.debug(
                "claude_call_success",
                agent=self.agent_name,
                input_length=len(prompt),
                output_length=len(content),
                usage=response.usage.model_dump() if hasattr(response, 'usage') else None,
            )
            
            return content
            
        except Exception as e:
            logger.error(
                "claude_call_failed",
                agent=self.agent_name,
                error=str(e),
            )
            raise
    
    async def call_claude_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Call Claude and parse JSON response.
        
        Args:
            prompt: User prompt (should request JSON output)
            system_prompt: Optional system prompt
            
        Returns:
            Parsed JSON response as dict
        """
        response = await self.call_claude(prompt, system_prompt)
        
        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(
                "json_parse_failed",
                agent=self.agent_name,
                error=str(e),
                response_preview=response[:200],
            )
            # Return empty dict on parse failure
            return {}
    
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method - to be implemented by subclasses.
        
        Args:
            context: Input context containing all necessary data
            
        Returns:
            Output context with agent's results
        """
        raise NotImplementedError(f"{self.agent_name} must implement run() method")
    
    def format_context(self, context: Dict[str, Any], fields: List[str]) -> str:
        """
        Format context fields into a readable string for prompts.
        
        Args:
            context: Input context dict
            fields: List of field names to include
            
        Returns:
            Formatted string
        """
        formatted = []
        for field in fields:
            value = context.get(field)
            if value:
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, indent=2)
                else:
                    value_str = str(value)
                
                # Truncate long values
                if len(value_str) > 2000:
                    value_str = value_str[:2000] + "\n... (truncated)"
                
                formatted.append(f"## {field}\n{value_str}\n")
        
        return "\n".join(formatted)
    
    def extract_code_blocks(self, content: str) -> Dict[str, str]:
        """
        Extract code blocks from response content.
        
        Expected format:
        ```filename: path/to/file.py
        <code>
        ```
        
        Returns:
            Dict mapping file paths to code content
        """
        code_files = {}
        lines = content.split("\n")
        current_file = None
        current_code = []
        
        for line in lines:
            if line.startswith("```filename:"):
                # Save previous file
                if current_file and current_code:
                    code_files[current_file] = "\n".join(current_code)
                    current_code = []
                
                # Extract new filename
                current_file = line.split("```filename:")[1].strip()
            
            elif line.startswith("```") and current_file:
                # End of code block
                if current_code:
                    code_files[current_file] = "\n".join(current_code)
                    current_code = []
                    current_file = None
            
            elif current_file:
                current_code.append(line)
        
        # Handle last file
        if current_file and current_code:
            code_files[current_file] = "\n".join(current_code)
        
        return code_files
    
    def log_result(self, status: str, **kwargs):
        """
        Log agent execution result.
        
        Args:
            status: "success", "failure", "warning"
            **kwargs: Additional context to log
        """
        logger.info(
            f"agent_{status}",
            agent=self.agent_name,
            **kwargs,
        )

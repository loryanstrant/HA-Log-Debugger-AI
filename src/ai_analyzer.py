"""AI analyzer service for processing log entries and generating recommendations."""

import asyncio
import logging
import json
from datetime import datetime
from typing import List, Optional
from openai import AsyncOpenAI
from .models import LogEntry, Recommendation

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI service for analyzing log entries and generating recommendations."""
    
    def __init__(self, 
                 endpoint_url: str,
                 api_key: str,
                 model_name: str = "gpt-3.5-turbo"):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=endpoint_url
        )
        self.model_name = model_name
        self.system_prompt = self._get_system_prompt()
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI model."""
        return """You are an expert Home Assistant troubleshooting assistant. Your role is to analyze error and warning messages from Home Assistant logs and provide helpful, actionable recommendations to resolve issues.

When analyzing log entries, please:

1. Identify the root cause of the issue
2. Provide specific, actionable steps to resolve the problem
3. Include relevant configuration examples when applicable
4. Suggest preventive measures if appropriate
5. Rate the severity as: LOW, MEDIUM, HIGH, or CRITICAL

Respond with a JSON object containing:
- "issue_summary": A brief description of the problem
- "recommendation": Detailed steps to fix the issue
- "severity": The severity level (LOW/MEDIUM/HIGH/CRITICAL)

Keep recommendations concise but comprehensive. Focus on practical solutions that users can implement."""
    
    async def analyze_log_entries(self, log_entries: List[LogEntry]) -> List[Recommendation]:
        """Analyze a batch of log entries and generate recommendations."""
        if not log_entries:
            return []
        
        recommendations = []
        
        # Group similar log entries to avoid duplicate analysis
        grouped_entries = self._group_similar_entries(log_entries)
        
        for group in grouped_entries:
            try:
                recommendation = await self._analyze_single_group(group)
                if recommendation:
                    recommendations.append(recommendation)
            except Exception as e:
                logger.error(f"Error analyzing log group: {e}")
                continue
        
        return recommendations
    
    def _group_similar_entries(self, log_entries: List[LogEntry]) -> List[List[LogEntry]]:
        """Group similar log entries to avoid duplicate processing."""
        groups = {}
        
        for entry in log_entries:
            # Create a grouping key based on component and message pattern
            key = f"{entry.level.value}:{entry.component}"
            
            # Simple message similarity (first 100 characters)
            message_key = entry.message[:100] if len(entry.message) > 100 else entry.message
            key += f":{hash(message_key)}"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(entry)
        
        return list(groups.values())
    
    async def _analyze_single_group(self, log_entries: List[LogEntry]) -> Optional[Recommendation]:
        """Analyze a single group of similar log entries."""
        if not log_entries:
            return None
        
        # Use the first entry as representative
        representative_entry = log_entries[0]
        
        # Create context for the AI
        context = self._create_analysis_context(log_entries)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.1,  # Low temperature for consistent responses
                max_tokens=1000
            )
            
            result = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                analysis = json.loads(result)
                
                # Generate hash for the log entry group
                log_hash = self._generate_group_hash(log_entries)
                
                return Recommendation(
                    log_entry_hash=log_hash,
                    issue_summary=analysis.get("issue_summary", "Unknown issue"),
                    recommendation=analysis.get("recommendation", "No specific recommendation available"),
                    severity=analysis.get("severity", "MEDIUM"),
                    created_at=datetime.now(),
                    resolved=False
                )
            
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse AI response as JSON: {result}")
                # Fallback to plain text response
                log_hash = self._generate_group_hash(log_entries)
                
                return Recommendation(
                    log_entry_hash=log_hash,
                    issue_summary=f"{representative_entry.level.value} in {representative_entry.component}",
                    recommendation=result,
                    severity="MEDIUM",
                    created_at=datetime.now(),
                    resolved=False
                )
        
        except Exception as e:
            logger.error(f"Error calling AI service: {e}")
            return None
    
    def _create_analysis_context(self, log_entries: List[LogEntry]) -> str:
        """Create context string for AI analysis."""
        context_parts = [
            "Please analyze the following Home Assistant log entries and provide recommendations:",
            ""
        ]
        
        # Include up to 5 entries from the group
        for i, entry in enumerate(log_entries[:5]):
            context_parts.append(f"Entry {i+1}:")
            context_parts.append(f"  Timestamp: {entry.timestamp}")
            context_parts.append(f"  Level: {entry.level.value}")
            if entry.component:
                context_parts.append(f"  Component: {entry.component}")
            context_parts.append(f"  Message: {entry.message}")
            context_parts.append("")
        
        if len(log_entries) > 5:
            context_parts.append(f"... and {len(log_entries) - 5} more similar entries")
            context_parts.append("")
        
        context_parts.append("Please provide your analysis in JSON format with issue_summary, recommendation, and severity fields.")
        
        return "\n".join(context_parts)
    
    def _generate_group_hash(self, log_entries: List[LogEntry]) -> str:
        """Generate a hash for a group of log entries."""
        import hashlib
        
        # Use the first entry to represent the group
        representative = log_entries[0]
        content = f"{representative.level.value}:{representative.component}:{representative.message[:200]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def test_connection(self) -> bool:
        """Test the AI service connection."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": "Hello, please respond with 'OK' if you can receive this message."}
                ],
                max_tokens=10
            )
            
            result = response.choices[0].message.content.strip()
            return "OK" in result.upper()
        
        except Exception as e:
            logger.error(f"AI service connection test failed: {e}")
            return False
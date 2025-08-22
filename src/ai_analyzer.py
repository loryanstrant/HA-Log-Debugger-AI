"""AI analyzer service for processing log entries and generating recommendations."""

import asyncio
import logging
import json
import re
from datetime import datetime
from typing import List, Optional
from openai import AsyncOpenAI
from .models import LogEntry, Recommendation
from .web_search import WebSearchService

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

You will be provided with:
- Log entry details (timestamp, level, component, message)
- Relevant Home Assistant documentation links
- Related GitHub issues from the Home Assistant core repository

Please respond with structured Markdown content in the following format:

# [Clear Issue Title]

## [Brief description of the problem as a subtitle]

**Severity:** [LOW/MEDIUM/HIGH/CRITICAL]

### Recommendations:
- [ ] [Specific actionable step 1]
- [ ] [Specific actionable step 2]
- [ ] [Additional steps as needed]

### Related Documentation:
[Include any provided documentation links with descriptive text]

### Similar Issues:
[Include any provided GitHub issue links with descriptive text]

### Additional Notes:
[Any additional context, configuration examples, or preventive measures]

Focus on practical solutions that users can implement. Use checkboxes for actionable items to make it easy for users to track their progress."""
    
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
        
        # Get contextual information from web search
        contextual_info = {}
        try:
            async with WebSearchService() as search_service:
                contextual_info = await search_service.get_contextual_information(
                    representative_entry.message,
                    representative_entry.component
                )
        except Exception as e:
            logger.warning(f"Failed to get contextual information: {e}")
            contextual_info = {'documentation': [], 'issues': []}
        
        # Create context for the AI
        context = self._create_analysis_context(log_entries, contextual_info)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.1,  # Low temperature for consistent responses
                max_tokens=2000  # Increased for markdown content
            )
            
            result = response.choices[0].message.content
            
            # Parse the markdown response to extract structured data
            try:
                parsed_data = self._parse_markdown_response(result)
                
                # Generate hash for the log entry group
                log_hash = self._generate_group_hash(log_entries)
                
                return Recommendation(
                    log_entry_hash=log_hash,
                    issue_summary=parsed_data.get("issue_summary", "Unknown issue"),
                    recommendation=result,  # Store the full markdown content
                    severity=parsed_data.get("severity", "MEDIUM"),
                    created_at=datetime.now(),
                    resolved=False
                )
            
            except Exception as e:
                logger.warning(f"Failed to parse markdown response: {e}")
                # Fallback handling
                log_hash = self._generate_group_hash(log_entries)
                
                # Try to extract severity from markdown if possible
                severity = self._extract_severity_from_markdown(result)
                issue_summary = self._extract_title_from_markdown(result)
                
                return Recommendation(
                    log_entry_hash=log_hash,
                    issue_summary=issue_summary or f"{representative_entry.level.value} in {representative_entry.component}",
                    recommendation=result,
                    severity=severity,
                    created_at=datetime.now(),
                    resolved=False
                )
        
        except Exception as e:
            logger.error(f"Error calling AI service: {e}")
            return None
    
    def _create_analysis_context(self, log_entries: List[LogEntry], contextual_info: dict = None) -> str:
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
        
        # Add contextual information if available
        if contextual_info:
            if contextual_info.get('documentation'):
                context_parts.append("Related Home Assistant Documentation:")
                for doc in contextual_info['documentation']:
                    context_parts.append(f"- {doc['title']}: {doc['url']}")
                    if doc.get('description'):
                        context_parts.append(f"  Description: {doc['description']}")
                context_parts.append("")
            
            if contextual_info.get('issues'):
                context_parts.append("Related GitHub Issues:")
                for issue in contextual_info['issues']:
                    context_parts.append(f"- #{issue['number']}: {issue['title']} ({issue['state']})")
                    context_parts.append(f"  URL: {issue['url']}")
                    if issue.get('description'):
                        context_parts.append(f"  Description: {issue['description']}")
                context_parts.append("")
        
        context_parts.append("Please provide your analysis in the structured Markdown format specified in the system prompt.")
        
        return "\n".join(context_parts)
    
    def _generate_group_hash(self, log_entries: List[LogEntry]) -> str:
        """Generate a hash for a group of log entries."""
        import hashlib
        
        # Use the first entry to represent the group
        representative = log_entries[0]
        content = f"{representative.level.value}:{representative.component}:{representative.message[:200]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _parse_markdown_response(self, markdown_content: str) -> dict:
        """Parse markdown response to extract structured data."""
        result = {
            "issue_summary": "Unknown issue",
            "severity": "MEDIUM"
        }
        
        # Extract title (first # heading)
        title_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            result["issue_summary"] = title
        
        # Extract subtitle (first ## heading)  
        subtitle_match = re.search(r'^##\s+(.+)$', markdown_content, re.MULTILINE)
        if subtitle_match:
            subtitle = subtitle_match.group(1).strip()
            result["issue_summary"] = subtitle  # Use subtitle as issue summary
        
        # Extract severity
        severity_match = re.search(r'\*\*Severity:\*\*\s*(\w+)', markdown_content, re.IGNORECASE)
        if severity_match:
            severity = severity_match.group(1).upper()
            if severity in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
                result["severity"] = severity
        
        return result
    
    def _extract_severity_from_markdown(self, content: str) -> str:
        """Extract severity from markdown content."""
        severity_match = re.search(r'\*\*Severity:\*\*\s*(\w+)', content, re.IGNORECASE)
        if severity_match:
            severity = severity_match.group(1).upper()
            if severity in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
                return severity
        return "MEDIUM"
    
    def _extract_title_from_markdown(self, content: str) -> Optional[str]:
        """Extract title/issue summary from markdown content."""
        # Try subtitle first (## heading)
        subtitle_match = re.search(r'^##\s+(.+)$', content, re.MULTILINE)
        if subtitle_match:
            return subtitle_match.group(1).strip()
        
        # Fallback to title (# heading)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip()
        
        return None
    
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
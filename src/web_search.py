"""Web search service for fetching contextual information from Home Assistant docs and GitHub issues."""

import asyncio
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import quote_plus
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebSearchService:
    """Service for searching Home Assistant documentation and GitHub issues."""
    
    def __init__(self):
        self.session = None
        self.base_ha_docs_url = "https://www.home-assistant.io/docs/"
        self.github_search_url = "https://api.github.com/search/issues"
        self.timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def search_ha_documentation(self, query: str, max_results: int = 3) -> List[Dict[str, str]]:
        """Search Home Assistant documentation for relevant content."""
        try:
            # Use Google's site-specific search for HA docs
            search_query = f"site:home-assistant.io/docs/ {query}"
            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with self.session.get(search_url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Failed to search HA docs: HTTP {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                results = []
                # Find search result links
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if 'home-assistant.io/docs/' in href and len(results) < max_results:
                        # Clean up the URL
                        if href.startswith('/url?q='):
                            href = href.split('/url?q=')[1].split('&')[0]
                        
                        if href.startswith('https://www.home-assistant.io/docs/'):
                            title = link.get_text().strip()
                            if title and len(title) > 5:  # Filter out short/empty titles
                                results.append({
                                    'title': title,
                                    'url': href,
                                    'description': await self._get_page_description(href)
                                })
                
                return results[:max_results]
        
        except Exception as e:
            logger.error(f"Error searching HA documentation: {e}")
            return []
    
    async def search_github_issues(self, query: str, max_results: int = 3) -> List[Dict[str, str]]:
        """Search GitHub issues in the home-assistant/core repository."""
        try:
            # Build GitHub API search query
            search_query = f"{query} repo:home-assistant/core is:issue"
            params = {
                'q': search_query,
                'sort': 'relevance',
                'order': 'desc',
                'per_page': max_results
            }
            
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'HA-Log-Debugger-AI'
            }
            
            async with self.session.get(self.github_search_url, params=params, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Failed to search GitHub issues: HTTP {response.status}")
                    return []
                
                data = await response.json()
                results = []
                
                for item in data.get('items', [])[:max_results]:
                    results.append({
                        'title': item.get('title', 'No title'),
                        'url': item.get('html_url', ''),
                        'description': item.get('body', '')[:200] + '...' if item.get('body') else 'No description',
                        'state': item.get('state', 'unknown'),
                        'number': item.get('number', 0)
                    })
                
                return results
        
        except Exception as e:
            logger.error(f"Error searching GitHub issues: {e}")
            return []
    
    async def _get_page_description(self, url: str) -> str:
        """Get a brief description from a web page."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    return "No description available"
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Try to get meta description first
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    return meta_desc['content'][:200]
                
                # Fallback to first paragraph
                first_p = soup.find('p')
                if first_p:
                    text = first_p.get_text().strip()
                    return text[:200] + '...' if len(text) > 200 else text
                
                return "No description available"
        
        except Exception as e:
            logger.debug(f"Error getting page description for {url}: {e}")
            return "No description available"
    
    async def get_contextual_information(self, log_entry_message: str, component: str = None) -> Dict[str, List[Dict[str, str]]]:
        """Get contextual information from both HA docs and GitHub issues."""
        # Extract relevant keywords from the log message
        search_terms = self._extract_search_terms(log_entry_message, component)
        
        # Search both sources concurrently
        ha_docs_task = self.search_ha_documentation(search_terms)
        github_issues_task = self.search_github_issues(search_terms)
        
        ha_docs, github_issues = await asyncio.gather(
            ha_docs_task, 
            github_issues_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(ha_docs, Exception):
            logger.error(f"Error in HA docs search: {ha_docs}")
            ha_docs = []
        
        if isinstance(github_issues, Exception):
            logger.error(f"Error in GitHub issues search: {github_issues}")
            github_issues = []
        
        return {
            'documentation': ha_docs,
            'issues': github_issues
        }
    
    def _extract_search_terms(self, message: str, component: str = None) -> str:
        """Extract relevant search terms from log message and component."""
        # Start with component if available
        terms = []
        if component:
            terms.append(component)
        
        # Extract key words from error message (ignore common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'cannot', 'cant', 'not'}
        
        # Remove common log patterns and extract meaningful words
        cleaned_message = re.sub(r'\d+\.\d+\.\d+\.\d+', '', message)  # Remove IP addresses
        cleaned_message = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', cleaned_message)  # Remove dates
        cleaned_message = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', '', cleaned_message)  # Remove times
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', cleaned_message.lower())
        meaningful_words = [word for word in words if word not in stop_words]
        
        # Take the most relevant words (first few and any that appear multiple times)
        word_counts = {}
        for word in meaningful_words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Priority words (appear multiple times or are at the beginning)
        priority_words = [word for word, count in word_counts.items() if count > 1]
        priority_words.extend(meaningful_words[:3])  # First 3 words
        
        terms.extend(priority_words[:5])  # Limit to 5 terms max
        
        return ' '.join(terms)
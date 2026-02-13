#!/usr/bin/env python3
"""
Hybrid Search: Vector + Keyword Search
Combines semantic vector search (via claude-mem) with keyword/FTS matching.
60% vector + 40% keyword by default.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Tuple

def get_workspace_dir() -> str:
    """Get workspace directory from environment or current working directory."""
    return os.environ.get('WORKSPACE_DIR', os.getcwd())

class HybridSearcher:
    def __init__(self, workspace_dir: str = None, vector_weight: float = 0.6, keyword_weight: float = 0.4):
        self.workspace_dir = workspace_dir or get_workspace_dir()
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.claude_mem_port = os.environ.get('CLAUDE_MEM_PORT', '37777')
        self.claude_mem_enabled = os.environ.get('CLAUDE_MEM_ENABLED', 'true').lower() == 'true'
        
    def keyword_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search items.json facts, summary.md files, and daily notes for exact keyword matches."""
        results = []
        query_lower = query.lower()
        
        # Search entity files
        entities_dir = Path(self.workspace_dir) / "life" / "areas"
        if entities_dir.exists():
            for entity_type in ["people", "companies", "projects"]:
                entity_type_dir = entities_dir / entity_type
                if entity_type_dir.exists():
                    for entity_dir in entity_type_dir.iterdir():
                        if entity_dir.is_dir():
                            self._search_entity_files(entity_dir, query_lower, results)
        
        # Search daily notes
        memory_dir = Path(self.workspace_dir) / "memory"
        if memory_dir.exists():
            for daily_note in memory_dir.glob("*.md"):
                self._search_daily_note(daily_note, query_lower, results)
        
        # Sort by relevance (exact matches first, then partial)
        results.sort(key=lambda x: (-x['score'], x['timestamp']), reverse=True)
        
        return results[:limit]
    
    def _search_entity_files(self, entity_dir: Path, query: str, results: List[Dict[str, Any]]):
        """Search both items.json and summary.md in an entity directory."""
        entity_name = entity_dir.name
        
        # Search items.json
        items_file = entity_dir / "items.json"
        if items_file.exists():
            try:
                with open(items_file, 'r') as f:
                    items = json.load(f)
                    for item in items:
                        if item.get('status') == 'active':
                            fact = item.get('fact', '').lower()
                            score = self._calculate_keyword_score(fact, query)
                            if score > 0:
                                results.append({
                                    'type': 'entity_fact',
                                    'entity': entity_name,
                                    'content': item['fact'],
                                    'score': score,
                                    'timestamp': item.get('timestamp', ''),
                                    'category': item.get('category', ''),
                                    'source': f"{entity_name}/items.json#{item.get('id', '')}"
                                })
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        # Search summary.md
        summary_file = entity_dir / "summary.md"
        if summary_file.exists():
            try:
                with open(summary_file, 'r') as f:
                    content = f.read().lower()
                    score = self._calculate_keyword_score(content, query)
                    if score > 0:
                        # Extract relevant snippet
                        snippet = self._extract_snippet(content, query)
                        results.append({
                            'type': 'entity_summary',
                            'entity': entity_name,
                            'content': snippet,
                            'score': score,
                            'timestamp': '',  # Summaries don't have timestamps
                            'category': 'summary',
                            'source': f"{entity_name}/summary.md"
                        })
            except FileNotFoundError:
                pass
    
    def _search_daily_note(self, daily_note: Path, query: str, results: List[Dict[str, Any]]):
        """Search a daily note file for keyword matches."""
        try:
            with open(daily_note, 'r') as f:
                content = f.read()
                content_lower = content.lower()
                score = self._calculate_keyword_score(content_lower, query)
                if score > 0:
                    snippet = self._extract_snippet(content_lower, query)
                    results.append({
                        'type': 'daily_note',
                        'entity': daily_note.stem,  # Date from filename
                        'content': snippet,
                        'score': score,
                        'timestamp': daily_note.stem,
                        'category': 'daily_event',
                        'source': f"memory/{daily_note.name}"
                    })
        except FileNotFoundError:
            pass
    
    def _calculate_keyword_score(self, text: str, query: str) -> float:
        """Calculate keyword match score based on exact and partial matches."""
        query_words = query.split()
        exact_matches = sum(1 for word in query_words if word in text)
        partial_matches = sum(1 for word in query_words if any(word in text_word for text_word in text.split()))
        
        # Exact phrase match gets highest score
        if query in text:
            return 1.0
        
        # Weighted score based on word matches
        if len(query_words) == 0:
            return 0.0
        
        exact_score = exact_matches / len(query_words)
        partial_score = partial_matches / len(query_words) * 0.5
        
        return min(exact_score + partial_score, 1.0)
    
    def _extract_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """Extract a relevant snippet around the keyword match."""
        query_pos = content.find(query.lower())
        if query_pos == -1:
            # Fallback to first occurrence of any query word
            query_words = query.lower().split()
            for word in query_words:
                pos = content.find(word)
                if pos != -1:
                    query_pos = pos
                    break
        
        if query_pos == -1:
            return content[:max_length] + "..." if len(content) > max_length else content
        
        # Extract context around the match
        start = max(0, query_pos - max_length // 2)
        end = min(len(content), query_pos + max_length // 2)
        snippet = content[start:end]
        
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def vector_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Query claude-mem worker API for semantic vector search."""
        if not self.claude_mem_enabled:
            return []
        
        try:
            # Query claude-mem API
            url = f"http://localhost:{self.claude_mem_port}/search"
            data = {
                'query': query,
                'limit': limit,
                'type': 'semantic'
            }
            
            req_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=req_data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                # Convert claude-mem format to our format
                vector_results = []
                for item in result.get('results', []):
                    vector_results.append({
                        'type': 'vector_match',
                        'entity': item.get('source', 'unknown'),
                        'content': item.get('content', '')[:300],  # Truncate long content
                        'score': item.get('score', 0.0),
                        'timestamp': item.get('timestamp', ''),
                        'category': 'semantic',
                        'source': f"claude-mem#{item.get('id', '')}"
                    })
                
                return vector_results
                
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, Exception) as e:
            # Claude-mem not available, return empty results
            return []
    
    def hybrid_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Combine vector and keyword search with weighted scoring."""
        # Get both types of results
        vector_results = self.vector_search(query, limit * 2)  # Get more to allow for blending
        keyword_results = self.keyword_search(query, limit * 2)
        
        # Create combined scoring
        all_results = []
        
        # Add vector results with weighted score
        for result in vector_results:
            result['final_score'] = result['score'] * self.vector_weight
            result['search_type'] = 'vector'
            all_results.append(result)
        
        # Add keyword results with weighted score
        for result in keyword_results:
            result['final_score'] = result['score'] * self.keyword_weight
            result['search_type'] = 'keyword'
            all_results.append(result)
        
        # Remove duplicates based on content similarity
        unique_results = self._deduplicate_results(all_results)
        
        # Sort by final score
        unique_results.sort(key=lambda x: x['final_score'], reverse=True)
        
        return unique_results[:limit]
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate results based on content similarity."""
        unique_results = []
        seen_content = set()
        
        for result in results:
            # Create a simplified content hash for dedup
            content_key = result['content'].lower().strip()[:100]  # First 100 chars
            
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_results.append(result)
        
        return unique_results

def main():
    parser = argparse.ArgumentParser(description="Hybrid Search: Vector + Keyword")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--vector-weight", type=float, default=0.6, 
                       help="Weight for vector search (0.0-1.0, default: 0.6)")
    parser.add_argument("--keyword-weight", type=float, default=0.4,
                       help="Weight for keyword search (0.0-1.0, default: 0.4)")
    parser.add_argument("--limit", type=int, default=10,
                       help="Maximum number of results (default: 10)")
    parser.add_argument("--keyword-only", action="store_true",
                       help="Use keyword search only (fallback mode)")
    parser.add_argument("--vector-only", action="store_true", 
                       help="Use vector search only")
    parser.add_argument("--workspace", help="Workspace directory")
    
    args = parser.parse_args()
    
    # Validate weights
    if not (0.0 <= args.vector_weight <= 1.0) or not (0.0 <= args.keyword_weight <= 1.0):
        print("Error: Weights must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(1)
    
    # Create searcher
    searcher = HybridSearcher(
        workspace_dir=args.workspace,
        vector_weight=args.vector_weight,
        keyword_weight=args.keyword_weight
    )
    
    # Perform search
    if args.keyword_only:
        results = searcher.keyword_search(args.query, args.limit)
        search_mode = "Keyword-only"
    elif args.vector_only:
        results = searcher.vector_search(args.query, args.limit)
        search_mode = "Vector-only"
    else:
        results = searcher.hybrid_search(args.query, args.limit)
        search_mode = f"Hybrid (vector: {args.vector_weight:.1f}, keyword: {args.keyword_weight:.1f})"
    
    # Output results
    print(f"# {search_mode} Search Results")
    print(f"Query: \"{args.query}\"")
    print(f"Found {len(results)} results\\n")
    
    for i, result in enumerate(results, 1):
        score_display = f"{result.get('final_score', result['score']):.3f}"
        print(f"## {i}. {result['entity']} [{score_display}]")
        print(f"**Type:** {result['type']} | **Category:** {result.get('category', 'N/A')}")
        if result.get('search_type'):
            print(f"**Search:** {result['search_type']}")
        print(f"**Source:** {result['source']}")
        if result.get('timestamp'):
            print(f"**Date:** {result['timestamp']}")
        print(f"\\n{result['content']}\\n")
        print("---\\n")
    
    if not results:
        print("No results found. Try:")
        print("- Different keywords")
        print("- Broader search terms") 
        print("- Check if claude-mem is running (for vector search)")

if __name__ == "__main__":
    main()
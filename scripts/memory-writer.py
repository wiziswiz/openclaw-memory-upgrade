#!/usr/bin/env python3
"""
Memory Writer: Read/Write Separation
Centralizes all memory write operations through a queue-based system.
Ensures main conversation loop only READs memory, writes go through this service.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib
import uuid

def get_workspace_dir() -> str:
    """Get workspace directory from environment or current working directory."""
    return os.environ.get('WORKSPACE_DIR', os.getcwd())

class MemoryWriter:
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = workspace_dir or get_workspace_dir()
        self.queue_file = Path(self.workspace_dir) / ".memory-write-queue.json"
        self.entities_dir = Path(self.workspace_dir) / "life" / "areas"
        self.memory_dir = Path(self.workspace_dir) / "memory"
        self.dedup_hashes_file = Path(self.workspace_dir) / ".memory-hashes.json"
        
        # Ensure directories exist
        self.entities_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
    
    def load_write_queue(self) -> List[Dict[str, Any]]:
        """Load pending write operations from queue file."""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []
    
    def save_write_queue(self, queue: List[Dict[str, Any]]):
        """Save write queue to disk."""
        with open(self.queue_file, 'w') as f:
            json.dump(queue, f, indent=2)
    
    def load_dedup_hashes(self) -> Dict[str, str]:
        """Load existing content hashes for deduplication."""
        if self.dedup_hashes_file.exists():
            try:
                with open(self.dedup_hashes_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def save_dedup_hashes(self, hashes: Dict[str, str]):
        """Save content hashes for deduplication."""
        with open(self.dedup_hashes_file, 'w') as f:
            json.dump(hashes, f, indent=2)
    
    def calculate_content_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content for deduplication."""
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]  # Short hash
    
    def check_duplicate(self, fact: str) -> bool:
        """Check if fact is a duplicate using hash comparison."""
        fact_hash = self.calculate_content_hash(fact)
        existing_hashes = self.load_dedup_hashes()
        return fact_hash in existing_hashes.values()
    
    def validate_write_request(self, request: Dict[str, Any]) -> tuple:
        """Validate a write request and return (is_valid, error_message)."""
        # Check required fields
        required_fields = ['operation', 'entity_path', 'data']
        for field in required_fields:
            if field not in request:
                return False, f"Missing required field: {field}"
        
        # Validate operation type
        valid_operations = ['write_fact', 'write_summary', 'write_daily_note', 'update_patterns']
        if request['operation'] not in valid_operations:
            return False, f"Invalid operation: {request['operation']}"
        
        # Validate entity path format
        entity_path = request['entity_path']
        if request['operation'] in ['write_fact', 'write_summary']:
            if not self._is_valid_entity_path(entity_path):
                return False, f"Invalid entity path format: {entity_path}"
        
        # Validate data structure based on operation
        if request['operation'] == 'write_fact':
            if not self._is_valid_fact_data(request['data']):
                return False, "Invalid fact data structure"
        
        return True, ""
    
    def _is_valid_entity_path(self, path: str) -> bool:
        """Check if entity path has valid format: type/name"""
        parts = path.split('/')
        return (len(parts) == 2 and 
                parts[0] in ['people', 'companies', 'projects'] and 
                len(parts[1]) > 0)
    
    def _is_valid_fact_data(self, data: Dict[str, Any]) -> bool:
        """Validate fact data structure."""
        required_fields = ['fact', 'category', 'type', 'timestamp', 'source']
        for field in required_fields:
            if field not in data:
                return False
        
        # Check field types and values
        if not isinstance(data['fact'], str) or len(data['fact']) < 3:
            return False
        
        if not isinstance(data['category'], str):
            return False
        
        if not isinstance(data['timestamp'], str):
            return False
        
        return True
    
    def queue_write(self, operation: str, entity_path: str, data: Dict[str, Any], 
                   priority: str = 'normal') -> Dict[str, Any]:
        """Queue a write operation."""
        # Create write request
        request = {
            'id': str(uuid.uuid4()),
            'operation': operation,
            'entity_path': entity_path,
            'data': data,
            'priority': priority,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        # Validate request
        is_valid, error_msg = self.validate_write_request(request)
        if not is_valid:
            return {
                'success': False,
                'error': error_msg,
                'request_id': None
            }
        
        # Check for duplicates if it's a fact
        if operation == 'write_fact' and self.check_duplicate(data['fact']):
            return {
                'success': False,
                'error': 'Duplicate fact detected',
                'request_id': request['id']
            }
        
        # Add to queue
        queue = self.load_write_queue()
        queue.append(request)
        
        # Sort by priority and timestamp
        priority_order = {'high': 0, 'normal': 1, 'low': 2}
        queue.sort(key=lambda x: (priority_order.get(x.get('priority', 'normal'), 1), 
                                 x['timestamp']))
        
        self.save_write_queue(queue)
        
        return {
            'success': True,
            'error': None,
            'request_id': request['id']
        }
    
    def get_entity_dir(self, entity_path: str) -> Path:
        """Get the directory path for an entity."""
        entity_type, entity_name = entity_path.split('/', 1)
        normalized_name = entity_name.lower().replace(' ', '-').replace('.', '')
        return self.entities_dir / entity_type / normalized_name
    
    def ensure_entity_exists(self, entity_path: str):
        """Ensure entity directory and base files exist."""
        entity_dir = self.get_entity_dir(entity_path)
        entity_dir.mkdir(parents=True, exist_ok=True)
        
        # Create items.json if it doesn't exist
        items_file = entity_dir / "items.json"
        if not items_file.exists():
            with open(items_file, 'w') as f:
                json.dump([], f, indent=2)
        
        # Create summary.md if it doesn't exist
        summary_file = entity_dir / "summary.md"
        if not summary_file.exists():
            entity_name = entity_path.split('/', 1)[1]
            with open(summary_file, 'w') as f:
                f.write(f"# {entity_name}\\n\\n*Auto-created entity*\\n")
    
    def write_fact(self, entity_path: str, fact_data: Dict[str, Any]) -> bool:
        """Write a fact to entity items.json file."""
        self.ensure_entity_exists(entity_path)
        entity_dir = self.get_entity_dir(entity_path)
        items_file = entity_dir / "items.json"
        
        # Load existing facts
        try:
            with open(items_file, 'r') as f:
                facts = json.load(f)
        except json.JSONDecodeError:
            facts = []
        
        # Ensure fact has required fields
        if 'id' not in fact_data:
            fact_data['id'] = str(uuid.uuid4())[:8]
        if 'status' not in fact_data:
            fact_data['status'] = 'active'
        if 'supersededBy' not in fact_data:
            fact_data['supersededBy'] = None
        
        # Add fact
        facts.append(fact_data)
        
        # Write back to file
        with open(items_file, 'w') as f:
            json.dump(facts, f, indent=2)
        
        # Update dedup hashes
        hashes = self.load_dedup_hashes()
        fact_hash = self.calculate_content_hash(fact_data['fact'])
        hashes[fact_data['id']] = fact_hash
        self.save_dedup_hashes(hashes)
        
        return True
    
    def write_summary(self, entity_path: str, summary_content: str) -> bool:
        """Write or update entity summary.md file."""
        self.ensure_entity_exists(entity_path)
        entity_dir = self.get_entity_dir(entity_path)
        summary_file = entity_dir / "summary.md"
        
        with open(summary_file, 'w') as f:
            f.write(summary_content)
        
        return True
    
    def write_daily_note(self, date: str, content: str) -> bool:
        """Write or append to daily note file."""
        daily_note_file = self.memory_dir / f"{date}.md"
        
        # If file exists, append; otherwise create
        mode = 'a' if daily_note_file.exists() else 'w'
        
        with open(daily_note_file, mode) as f:
            if mode == 'a':
                f.write('\\n\\n')  # Add spacing before new content
            f.write(content)
        
        return True
    
    def update_patterns(self, patterns_data: Dict[str, Any]) -> bool:
        """Update patterns.json file."""
        patterns_file = Path(self.workspace_dir) / "patterns.json"
        
        # Load existing patterns or create new structure
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r') as f:
                    existing_patterns = json.load(f)
            except json.JSONDecodeError:
                existing_patterns = {}
        else:
            existing_patterns = {}
        
        # Merge with new patterns
        existing_patterns.update(patterns_data)
        
        # Write back to file
        with open(patterns_file, 'w') as f:
            json.dump(existing_patterns, f, indent=2)
        
        return True
    
    def process_write_request(self, request: Dict[str, Any]) -> bool:
        """Process a single write request from the queue."""
        try:
            operation = request['operation']
            entity_path = request['entity_path']
            data = request['data']
            
            if operation == 'write_fact':
                return self.write_fact(entity_path, data)
            elif operation == 'write_summary':
                return self.write_summary(entity_path, data.get('content', ''))
            elif operation == 'write_daily_note':
                return self.write_daily_note(data.get('date', ''), data.get('content', ''))
            elif operation == 'update_patterns':
                return self.update_patterns(data)
            else:
                return False
                
        except Exception as e:
            print(f"Error processing write request {request.get('id', 'unknown')}: {e}", file=sys.stderr)
            return False
    
    def flush_queue(self) -> Dict[str, Any]:
        """Process all pending write requests in the queue."""
        queue = self.load_write_queue()
        
        if not queue:
            return {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }
        
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        processed_queue = []
        
        for request in queue:
            if request.get('status') != 'pending':
                processed_queue.append(request)  # Keep non-pending requests
                continue
            
            results['processed'] += 1
            
            success = self.process_write_request(request)
            
            if success:
                request['status'] = 'completed'
                request['completed_at'] = datetime.now().isoformat()
                results['successful'] += 1
            else:
                request['status'] = 'failed'
                request['failed_at'] = datetime.now().isoformat()
                results['failed'] += 1
                results['errors'].append(f"Request {request['id']}: {request['operation']} failed")
            
            processed_queue.append(request)
        
        # Keep only recent completed/failed requests (last 100)
        completed_failed = [r for r in processed_queue if r.get('status') in ['completed', 'failed']]
        pending = [r for r in processed_queue if r.get('status') == 'pending']
        
        # Keep last 100 completed/failed + all pending
        if len(completed_failed) > 100:
            completed_failed = completed_failed[-100:]
        
        final_queue = pending + completed_failed
        self.save_write_queue(final_queue)
        
        return results
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        queue = self.load_write_queue()
        
        status_counts = {}
        for request in queue:
            status = request.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        priority_counts = {}
        pending_by_priority = {}
        for request in queue:
            if request.get('status') == 'pending':
                priority = request.get('priority', 'normal')
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
                if priority not in pending_by_priority:
                    pending_by_priority[priority] = []
                pending_by_priority[priority].append(request)
        
        return {
            'total_requests': len(queue),
            'status_breakdown': status_counts,
            'pending_by_priority': {k: len(v) for k, v in pending_by_priority.items()},
            'oldest_pending': min([r['timestamp'] for r in queue if r.get('status') == 'pending'], default=None)
        }

def main():
    parser = argparse.ArgumentParser(description="Memory Writer: Read/Write Separation")
    parser.add_argument("action", choices=['write', 'queue', 'flush', 'status'], 
                       help="Action to perform")
    parser.add_argument("entity_path", nargs='?', 
                       help="Entity path (type/name) for write operations")
    parser.add_argument("fact_json", nargs='?',
                       help="JSON string containing fact data for write operations")
    parser.add_argument("--priority", choices=['high', 'normal', 'low'], default='normal',
                       help="Priority for write operations")
    parser.add_argument("--workspace", help="Workspace directory")
    
    args = parser.parse_args()
    
    # Create memory writer
    writer = MemoryWriter(workspace_dir=args.workspace)
    
    if args.action == 'write':
        if not args.entity_path or not args.fact_json:
            print("Error: write action requires entity_path and fact_json arguments", file=sys.stderr)
            sys.exit(1)
        
        try:
            fact_data = json.loads(args.fact_json)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in fact_json: {e}", file=sys.stderr)
            sys.exit(1)
        
        result = writer.queue_write('write_fact', args.entity_path, fact_data, args.priority)
        
        if result['success']:
            print(f"Queued fact for {args.entity_path}")
            print(f"Request ID: {result['request_id']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
    
    elif args.action == 'queue':
        status = writer.get_queue_status()
        
        print("Memory Write Queue Status:")
        print(f"Total requests: {status['total_requests']}")
        print("\\nStatus breakdown:")
        for status_name, count in status['status_breakdown'].items():
            print(f"  {status_name}: {count}")
        
        if status['pending_by_priority']:
            print("\\nPending by priority:")
            for priority, count in status['pending_by_priority'].items():
                print(f"  {priority}: {count}")
        
        if status['oldest_pending']:
            print(f"\\nOldest pending: {status['oldest_pending']}")
    
    elif args.action == 'flush':
        print("Processing write queue...")
        results = writer.flush_queue()
        
        print(f"Processed: {results['processed']} requests")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        
        if results['errors']:
            print("\\nErrors:")
            for error in results['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(results['errors']) > 10:
                print(f"  ... and {len(results['errors']) - 10} more errors")
    
    elif args.action == 'status':
        status = writer.get_queue_status()
        
        print(f"Queue status: {status['total_requests']} total requests")
        
        pending_count = status['status_breakdown'].get('pending', 0)
        if pending_count > 0:
            print(f"⚠️  {pending_count} pending writes - run 'memory-writer.py flush' to process")
        else:
            print("✅ No pending writes")
        
        completed_count = status['status_breakdown'].get('completed', 0)
        failed_count = status['status_breakdown'].get('failed', 0)
        
        if completed_count > 0:
            print(f"✅ {completed_count} completed writes")
        if failed_count > 0:
            print(f"❌ {failed_count} failed writes")

if __name__ == "__main__":
    main()
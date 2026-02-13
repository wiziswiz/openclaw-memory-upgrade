#!/usr/bin/env python3
"""
Memory Deduplication Engine - Prevents duplicate memory storage
Uses SHA-256 hashing of normalized content to detect duplicates
"""

import json
import os
import sys
import hashlib
import glob
import re
from pathlib import Path
from datetime import datetime

# Configurable workspace directory
WORKSPACE_DIR = Path(os.environ.get('WORKSPACE_DIR', os.getcwd()))
HASH_INDEX_FILE = WORKSPACE_DIR / ".memory-hashes.json"

def normalize_text(text):
    """Normalize text for consistent hashing"""
    # Convert to lowercase
    text = text.lower()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove punctuation variations that don't change meaning
    text = re.sub(r'[.!?,;:]+', '', text)
    # Remove common articles/prepositions that don't change core meaning
    text = re.sub(r'\b(a|an|the|in|on|at|to|for|of|with|by)\b', '', text)
    return text.strip()

def get_content_hash(text):
    """Generate SHA-256 hash of normalized text"""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def load_hash_index():
    """Load existing hash index"""
    try:
        with open(HASH_INDEX_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_hash_index(hash_index):
    """Save hash index to disk"""
    try:
        HASH_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HASH_INDEX_FILE, 'w') as f:
            json.dump(hash_index, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving hash index: {e}")
        return False

def is_duplicate(content, hash_index=None):
    """Check if content is a duplicate"""
    if hash_index is None:
        hash_index = load_hash_index()
    
    content_hash = get_content_hash(content)
    return content_hash in hash_index

def add_to_index(content, source_file=None, hash_index=None):
    """Add content hash to index"""
    if hash_index is None:
        hash_index = load_hash_index()
    
    content_hash = get_content_hash(content)
    hash_index[content_hash] = {
        'first_seen': datetime.now().isoformat(),
        'source': source_file,
        'normalized': normalize_text(content)[:100] + "..." if len(normalize_text(content)) > 100 else normalize_text(content)
    }
    
    return hash_index, content_hash

def check_content(content):
    """Check if content is duplicate and return result"""
    hash_index = load_hash_index()
    content_hash = get_content_hash(content)
    
    if content_hash in hash_index:
        return {
            'is_duplicate': True,
            'hash': content_hash,
            'first_seen': hash_index[content_hash].get('first_seen'),
            'original_source': hash_index[content_hash].get('source')
        }
    else:
        return {
            'is_duplicate': False,
            'hash': content_hash
        }

def scan_for_duplicates():
    """Scan all existing memory files for duplicates"""
    hash_index = {}
    duplicates_found = []
    total_processed = 0
    
    print("Scanning for duplicates...")
    
    # Scan items.json files
    for items_file in WORKSPACE_DIR.rglob("items.json"):
        try:
            with open(items_file, 'r') as f:
                items = json.load(f)
            
            for item in items:
                fact = item.get('fact', '')
                if not fact:
                    continue
                
                total_processed += 1
                content_hash = get_content_hash(fact)
                
                if content_hash in hash_index:
                    duplicates_found.append({
                        'original_file': hash_index[content_hash]['source'],
                        'duplicate_file': str(items_file),
                        'content': fact[:100] + "..." if len(fact) > 100 else fact,
                        'hash': content_hash
                    })
                else:
                    hash_index[content_hash] = {
                        'first_seen': item.get('timestamp', datetime.now().strftime('%Y-%m-%d')),
                        'source': str(items_file),
                        'normalized': normalize_text(fact)[:100] + "..." if len(normalize_text(fact)) > 100 else normalize_text(fact)
                    }
                    
        except Exception as e:
            print(f"Error processing {items_file}: {e}")
    
    # Scan daily notes
    memory_dir = WORKSPACE_DIR / "memory"
    if memory_dir.exists():
        for note_file in memory_dir.glob("*.md"):
            try:
                with open(note_file, 'r') as f:
                    content = f.read()
                
                # Split into paragraphs and check each
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                
                for paragraph in paragraphs:
                    if len(paragraph) < 20:  # Skip very short content
                        continue
                        
                    total_processed += 1
                    content_hash = get_content_hash(paragraph)
                    
                    if content_hash in hash_index:
                        duplicates_found.append({
                            'original_file': hash_index[content_hash]['source'],
                            'duplicate_file': str(note_file),
                            'content': paragraph[:100] + "..." if len(paragraph) > 100 else paragraph,
                            'hash': content_hash
                        })
                    else:
                        hash_index[content_hash] = {
                            'first_seen': note_file.stem,  # Use filename as date
                            'source': str(note_file),
                            'normalized': normalize_text(paragraph)[:100] + "..." if len(normalize_text(paragraph)) > 100 else normalize_text(paragraph)
                        }
                        
            except Exception as e:
                print(f"Error processing {note_file}: {e}")
    
    # Save the updated hash index
    save_hash_index(hash_index)
    
    return {
        'total_processed': total_processed,
        'duplicates_found': len(duplicates_found),
        'duplicates': duplicates_found,
        'hash_index_size': len(hash_index)
    }

def show_duplicate_report(duplicates):
    """Show detailed duplicate report"""
    print(f"\nDuplicate Report:")
    print("-" * 60)
    
    if not duplicates['duplicates']:
        print("No duplicates found!")
        return
    
    for i, dup in enumerate(duplicates['duplicates'], 1):
        print(f"\nDuplicate #{i}:")
        print(f"  Original: {dup['original_file']}")
        print(f"  Duplicate: {dup['duplicate_file']}")
        print(f"  Content: {dup['content']}")
        print(f"  Hash: {dup['hash'][:12]}...")

def show_help():
    """Show usage information"""
    print(f"""
Memory Deduplication Engine

WORKSPACE: {WORKSPACE_DIR}

USAGE:
    memory-dedup.py check <text>        # Check if text is duplicate
    memory-dedup.py scan               # Scan all files for duplicates
    memory-dedup.py rebuild            # Rebuild hash index from scratch
    memory-dedup.py stats              # Show hash index statistics
    memory-dedup.py clean              # Remove hash index
    memory-dedup.py --help             # Show this help

DESCRIPTION:
    Maintains a SHA-256 hash index of normalized memory content to prevent
    storing the same information multiple times across daily notes and items.json files.

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
""")

def show_stats():
    """Show hash index statistics"""
    hash_index = load_hash_index()
    
    if not hash_index:
        print("No hash index found. Run 'scan' first.")
        return
    
    print(f"\nHash Index Statistics:")
    print("-" * 30)
    print(f"Total unique hashes: {len(hash_index)}")
    
    # Count by source type
    source_types = {}
    for entry in hash_index.values():
        source = entry.get('source', 'unknown')
        if 'items.json' in source:
            source_type = 'items.json'
        elif '.md' in source:
            source_type = 'daily_notes'
        else:
            source_type = 'other'
        
        source_types[source_type] = source_types.get(source_type, 0) + 1
    
    for source_type, count in source_types.items():
        print(f"{source_type}: {count}")
    
    print(f"\nIndex file: {HASH_INDEX_FILE}")
    print(f"Index size: {HASH_INDEX_FILE.stat().st_size if HASH_INDEX_FILE.exists() else 0} bytes")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == 'check':
        if len(sys.argv) < 3:
            print("Usage: memory-dedup.py check <text>")
            return
        
        text = ' '.join(sys.argv[2:])
        result = check_content(text)
        
        if result['is_duplicate']:
            print(f"DUPLICATE FOUND!")
            print(f"Hash: {result['hash'][:12]}...")
            print(f"First seen: {result['first_seen']}")
            print(f"Original source: {result['original_source']}")
        else:
            print(f"NOT a duplicate")
            print(f"Hash: {result['hash'][:12]}...")
    
    elif command in ['scan', 'rebuild']:
        results = scan_for_duplicates()
        
        print(f"\nScan Results:")
        print(f"Total items processed: {results['total_processed']}")
        print(f"Duplicates found: {results['duplicates_found']}")
        print(f"Hash index size: {results['hash_index_size']}")
        
        if results['duplicates_found'] > 0:
            show_report = input(f"\nShow detailed duplicate report? (y/n): ")
            if show_report.lower() == 'y':
                show_duplicate_report(results)
    
    elif command == 'stats':
        show_stats()
    
    elif command == 'clean':
        if HASH_INDEX_FILE.exists():
            HASH_INDEX_FILE.unlink()
            print(f"Removed hash index: {HASH_INDEX_FILE}")
        else:
            print("No hash index to clean")
    
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
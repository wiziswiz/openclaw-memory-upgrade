#!/usr/bin/env python3
"""
Memory Typing System - Adds type classification to items.json schema
Supports: profile | event | knowledge | behavior | skill | tool
"""

import json
import os
import sys
import glob
import re
from pathlib import Path
from datetime import datetime

# Configurable workspace directory
WORKSPACE_DIR = Path(os.environ.get('WORKSPACE_DIR', os.getcwd()))

# Content patterns for auto-classification
TYPE_PATTERNS = {
    'profile': [
        r'\b(name|lives in|works at|email|phone|title|role|background)\b',
        r'\b(personal|contact|demographic|bio)\b',
        r'\b(age|location|occupation|education)\b'
    ],
    'event': [
        r'\b(happened|occurred|on|during|meeting|call|conversation)\b',
        r'\b(launched|released|announced|delivered|completed)\b',
        r'\b(signed|closed|opened|started|finished)\b',
        r'\b(yesterday|today|tomorrow|last week|next week)\b'
    ],
    'knowledge': [
        r'\b(knows|understands|familiar with|experience with)\b',
        r'\b(API|documentation|process|procedure|method)\b',
        r'\b(learned|discovered|found out|research)\b'
    ],
    'behavior': [
        r'\b(prefers|likes|dislikes|always|never|usually)\b',
        r'\b(pattern|habit|routine|style|workflow)\b',
        r'\b(tends to|often|rarely|frequently)\b'
    ],
    'skill': [
        r'\b(can|able to|knows how|proficient|expert)\b',
        r'\b(programming|coding|design|analysis|management)\b',
        r'\b(technical|creative|strategic|analytical)\b'
    ],
    'tool': [
        r'\b(uses|tool|software|platform|service|API)\b',
        r'\b(integration|plugin|extension|app)\b',
        r'\b(configured|setup|installed|connected)\b'
    ]
}

def classify_fact_type(fact):
    """Auto-classify a fact by content patterns"""
    fact_lower = fact.lower()
    
    scores = {}
    for fact_type, patterns in TYPE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, fact_lower):
                score += 1
        scores[fact_type] = score
    
    # Return type with highest score, or 'knowledge' as default
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return 'knowledge'

def migrate_items_json(file_path, dry_run=False):
    """Add type field to items.json file"""
    try:
        with open(file_path, 'r') as f:
            items = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False, f"Error reading {file_path}"
    
    changes = 0
    for item in items:
        if 'type' not in item:
            item['type'] = classify_fact_type(item['fact'])
            changes += 1
    
    if not dry_run and changes > 0:
        try:
            with open(file_path, 'w') as f:
                json.dump(items, f, indent=4)
        except Exception as e:
            return False, f"Error writing {file_path}: {e}"
    
    return True, f"Updated {changes} items in {file_path}"

def find_all_items_json():
    """Find all items.json files in the workspace"""
    return list(WORKSPACE_DIR.rglob("items.json"))

def tag_item(entity, item_id, item_type, workspace_path=None):
    """Tag a specific item with a type"""
    if workspace_path is None:
        workspace_path = WORKSPACE_DIR
    
    # Find the items.json file for this entity
    items_files = list(workspace_path.rglob("items.json"))
    
    for file_path in items_files:
        try:
            with open(file_path, 'r') as f:
                items = json.load(f)
            
            for item in items:
                if item.get('id') == item_id:
                    item['type'] = item_type
                    
                    with open(file_path, 'w') as f:
                        json.dump(items, f, indent=4)
                    
                    return True, f"Tagged {item_id} as {item_type} in {file_path}"
        except Exception as e:
            continue
    
    return False, f"Item {item_id} not found in any items.json file"

def show_help():
    """Show usage information"""
    print(f"""
Memory Typing System

WORKSPACE: {WORKSPACE_DIR}

USAGE:
    memory-typing.py migrate [--dry-run]     # Migrate all items.json files
    memory-typing.py tag <item-id> <type>    # Tag specific item
    memory-typing.py classify <text>         # Test classification
    memory-typing.py stats                   # Show type distribution
    memory-typing.py --help                  # Show this help

TYPES:
    profile    Personal/contact information
    event      Things that happened/occur
    knowledge  Facts and information
    behavior   Patterns and preferences  
    skill      Capabilities and expertise
    tool       Software/services/integrations

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
""")

def show_stats():
    """Show type distribution across all items"""
    type_counts = {}
    total_items = 0
    
    for file_path in WORKSPACE_DIR.rglob("items.json"):
        try:
            with open(file_path, 'r') as f:
                items = json.load(f)
            
            for item in items:
                total_items += 1
                item_type = item.get('type', 'untyped')
                type_counts[item_type] = type_counts.get(item_type, 0) + 1
        except:
            continue
    
    print(f"\nMemory Type Distribution ({total_items} total items):")
    print("-" * 40)
    for item_type, count in sorted(type_counts.items()):
        percentage = (count / total_items) * 100 if total_items > 0 else 0
        print(f"{item_type:10s} {count:4d} ({percentage:5.1f}%)")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == 'migrate':
        dry_run = '--dry-run' in sys.argv
        items_files = find_all_items_json()
        
        print(f"Found {len(items_files)} items.json files")
        if dry_run:
            print("DRY RUN - no files will be modified")
        
        for file_path in items_files:
            success, message = migrate_items_json(file_path, dry_run)
            print(message)
    
    elif command == 'tag':
        if len(sys.argv) < 4:
            print("Usage: memory-typing.py tag <item-id> <type>")
            return
        
        item_id = sys.argv[2]
        item_type = sys.argv[3]
        
        if item_type not in TYPE_PATTERNS.keys():
            print(f"Invalid type. Must be one of: {', '.join(TYPE_PATTERNS.keys())}")
            return
        
        success, message = tag_item(None, item_id, item_type)
        print(message)
    
    elif command == 'classify':
        if len(sys.argv) < 3:
            print("Usage: memory-typing.py classify <text>")
            return
        
        text = ' '.join(sys.argv[2:])
        result = classify_fact_type(text)
        print(f"Classification: {result}")
        print(f"Text: {text}")
    
    elif command == 'stats':
        show_stats()
    
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
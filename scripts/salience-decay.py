#!/usr/bin/env python3
"""
Salience Decay System - Manages memory importance scoring over time
Adds lastAccessed and accessCount to items.json schema
Decay formula: score = recency_weight(lastAccessed) × log(accessCount + 1)
"""

import json
import os
import sys
import math
from datetime import datetime, timedelta
from pathlib import Path

# Configurable workspace directory
WORKSPACE_DIR = Path(os.environ.get('WORKSPACE_DIR', os.getcwd()))

def calculate_recency_weight(last_accessed_date, max_days=365):
    """Calculate recency weight (1.0 = today, 0.0 = max_days ago or older)"""
    try:
        if isinstance(last_accessed_date, str):
            last_accessed = datetime.fromisoformat(last_accessed_date.split('T')[0])
        else:
            last_accessed = last_accessed_date
        
        now = datetime.now()
        days_ago = (now - last_accessed).days
        
        if days_ago >= max_days:
            return 0.0
        
        # Exponential decay: more recent = higher weight
        return math.exp(-days_ago / (max_days / 3))
    
    except (ValueError, TypeError):
        return 0.1  # Default low weight for invalid dates

def calculate_salience_score(last_accessed, access_count):
    """Calculate salience score using the decay formula"""
    recency_weight = calculate_recency_weight(last_accessed)
    frequency_weight = math.log(access_count + 1)
    
    return recency_weight * frequency_weight

def update_item_access(items, item_id):
    """Update lastAccessed and accessCount for a specific item"""
    for item in items:
        if item.get('id') == item_id:
            now = datetime.now().isoformat()
            item['lastAccessed'] = now
            item['accessCount'] = item.get('accessCount', 0) + 1
            return True
    return False

def migrate_items_for_salience(file_path, dry_run=False):
    """Add salience fields to items.json file if missing"""
    try:
        with open(file_path, 'r') as f:
            items = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False, f"Error reading {file_path}"
    
    changes = 0
    for item in items:
        modified = False
        
        # Add lastAccessed if missing (use original timestamp or today)
        if 'lastAccessed' not in item:
            # Use original timestamp if available, otherwise use today
            original_date = item.get('timestamp', datetime.now().strftime('%Y-%m-%d'))
            item['lastAccessed'] = original_date
            modified = True
        
        # Add accessCount if missing (default to 1)
        if 'accessCount' not in item:
            item['accessCount'] = 1
            modified = True
        
        if modified:
            changes += 1
    
    if not dry_run and changes > 0:
        try:
            with open(file_path, 'w') as f:
                json.dump(items, f, indent=4)
        except Exception as e:
            return False, f"Error writing {file_path}: {e}"
    
    return True, f"Updated {changes} items in {file_path}"

def get_entity_items_by_salience(entity_path, limit=None):
    """Get items for an entity sorted by salience score"""
    items_file = Path(entity_path) / "items.json"
    
    try:
        with open(items_file, 'r') as f:
            items = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    # Calculate salience scores
    scored_items = []
    for item in items:
        last_accessed = item.get('lastAccessed', item.get('timestamp', '1970-01-01'))
        access_count = item.get('accessCount', 1)
        
        score = calculate_salience_score(last_accessed, access_count)
        
        scored_items.append({
            **item,
            'salience_score': round(score, 4)
        })
    
    # Sort by salience score (highest first)
    scored_items.sort(key=lambda x: x['salience_score'], reverse=True)
    
    if limit:
        scored_items = scored_items[:limit]
    
    return scored_items

def run_decay_sweep():
    """Run periodic decay sweep across all entities"""
    results = {
        'files_processed': 0,
        'items_updated': 0,
        'errors': []
    }
    
    for items_file in WORKSPACE_DIR.rglob("items.json"):
        try:
            success, message = migrate_items_for_salience(items_file)
            results['files_processed'] += 1
            
            if success:
                # Count updated items from message
                if 'Updated' in message:
                    updated_count = int(message.split('Updated ')[1].split(' items')[0])
                    results['items_updated'] += updated_count
            else:
                results['errors'].append(message)
                
        except Exception as e:
            results['errors'].append(f"Error processing {items_file}: {e}")
    
    return results

def access_item(entity_name, item_id):
    """Record access to a specific item (updates lastAccessed and accessCount)"""
    # Find the items.json file for this entity
    for items_file in WORKSPACE_DIR.rglob("items.json"):
        if entity_name.lower() in str(items_file).lower():
            try:
                with open(items_file, 'r') as f:
                    items = json.load(f)
                
                if update_item_access(items, item_id):
                    with open(items_file, 'w') as f:
                        json.dump(items, f, indent=4)
                    
                    return True, f"Updated access for {item_id} in {items_file}"
                    
            except Exception as e:
                continue
    
    return False, f"Item {item_id} not found for entity {entity_name}"

def show_entity_salience(entity_name, limit=10):
    """Show salience-ranked items for an entity"""
    # Find entity directory
    entity_paths = []
    for area_type in ['people', 'companies', 'projects', 'tools', 'hardware']:
        area_path = WORKSPACE_DIR / "life" / "areas" / area_type
        if area_path.exists():
            for entity_dir in area_path.iterdir():
                if entity_dir.is_dir() and entity_name.lower() in entity_dir.name.lower():
                    entity_paths.append(entity_dir)
    
    if not entity_paths:
        return f"Entity '{entity_name}' not found"
    
    results = []
    for entity_path in entity_paths:
        items = get_entity_items_by_salience(entity_path, limit)
        if items:
            results.append({
                'entity_path': str(entity_path),
                'items': items
            })
    
    return results

def show_salience_stats():
    """Show overall salience statistics"""
    stats = {
        'total_items': 0,
        'items_with_salience': 0,
        'avg_access_count': 0,
        'high_salience_items': 0,  # score > 1.0
        'low_salience_items': 0,   # score < 0.1
    }
    
    all_scores = []
    all_access_counts = []
    
    for items_file in WORKSPACE_DIR.rglob("items.json"):
        try:
            with open(items_file, 'r') as f:
                items = json.load(f)
            
            for item in items:
                stats['total_items'] += 1
                
                if 'lastAccessed' in item and 'accessCount' in item:
                    stats['items_with_salience'] += 1
                    
                    score = calculate_salience_score(
                        item['lastAccessed'], 
                        item['accessCount']
                    )
                    all_scores.append(score)
                    all_access_counts.append(item['accessCount'])
                    
                    if score > 1.0:
                        stats['high_salience_items'] += 1
                    elif score < 0.1:
                        stats['low_salience_items'] += 1
        except:
            continue
    
    if all_access_counts:
        stats['avg_access_count'] = round(sum(all_access_counts) / len(all_access_counts), 2)
        stats['avg_salience_score'] = round(sum(all_scores) / len(all_scores), 4)
        stats['max_salience_score'] = round(max(all_scores), 4)
    
    return stats

def show_help():
    """Show usage information"""
    print(f"""
Salience Decay System - Memory importance scoring

WORKSPACE: {WORKSPACE_DIR}

USAGE:
    salience-decay.py migrate                    # Add salience fields to all items
    salience-decay.py sweep                      # Run periodic decay sweep  
    salience-decay.py entity <name> [--limit N] # Show top items for entity
    salience-decay.py access <entity> <item-id> # Record item access
    salience-decay.py stats                     # Show salience statistics
    salience-decay.py score <last_accessed> <access_count> # Calculate score
    salience-decay.py --help                    # Show this help

EXAMPLES:
    salience-decay.py entity john --limit 5
    salience-decay.py access john john-001
    salience-decay.py score 2026-02-01 5
    
SALIENCE FORMULA:
    score = recency_weight(lastAccessed) × log(accessCount + 1)
    
    Where:
    - recency_weight: 1.0 (today) → 0.0 (1 year ago)
    - accessCount: Number of times item was accessed

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
""")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == 'migrate':
        results = run_decay_sweep()
        print(f"Migration completed:")
        print(f"Files processed: {results['files_processed']}")
        print(f"Items updated: {results['items_updated']}")
        if results['errors']:
            print(f"Errors: {len(results['errors'])}")
            for error in results['errors'][:5]:  # Show first 5 errors
                print(f"  {error}")
    
    elif command == 'sweep':
        results = run_decay_sweep()
        print(f"Decay sweep completed:")
        print(f"Files processed: {results['files_processed']}")
        print(f"Items updated: {results['items_updated']}")
        if results['errors']:
            print(f"Errors: {len(results['errors'])}")
    
    elif command == 'entity':
        if len(sys.argv) < 3:
            print("Usage: salience-decay.py entity <name> [--limit N]")
            return
        
        entity_name = sys.argv[2]
        limit = 10
        
        if '--limit' in sys.argv:
            try:
                limit_idx = sys.argv.index('--limit')
                limit = int(sys.argv[limit_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --limit value")
                return
        
        results = show_entity_salience(entity_name, limit)
        
        if isinstance(results, str):
            print(results)
        else:
            for result in results:
                print(f"\n{result['entity_path']}:")
                print("-" * 50)
                for i, item in enumerate(result['items'], 1):
                    print(f"{i:2d}. [{item['salience_score']}] {item['fact'][:80]}...")
                    print(f"     ID: {item['id']} | Access: {item.get('accessCount', 1)}x | Last: {item.get('lastAccessed', 'N/A')}")
    
    elif command == 'access':
        if len(sys.argv) < 4:
            print("Usage: salience-decay.py access <entity> <item-id>")
            return
        
        entity_name = sys.argv[2]
        item_id = sys.argv[3]
        
        success, message = access_item(entity_name, item_id)
        print(message)
    
    elif command == 'stats':
        stats = show_salience_stats()
        
        print(f"\nSalience System Statistics:")
        print("-" * 30)
        print(f"Total items: {stats['total_items']}")
        print(f"Items with salience data: {stats['items_with_salience']}")
        print(f"Coverage: {round(stats['items_with_salience']/stats['total_items']*100, 1) if stats['total_items'] > 0 else 0}%")
        
        if 'avg_salience_score' in stats:
            print(f"\nSalience Scores:")
            print(f"Average: {stats['avg_salience_score']}")
            print(f"Maximum: {stats['max_salience_score']}")
            print(f"High salience items (>1.0): {stats['high_salience_items']}")
            print(f"Low salience items (<0.1): {stats['low_salience_items']}")
        
        if 'avg_access_count' in stats:
            print(f"\nAccess Patterns:")
            print(f"Average access count: {stats['avg_access_count']}")
    
    elif command == 'score':
        if len(sys.argv) < 4:
            print("Usage: salience-decay.py score <last_accessed> <access_count>")
            return
        
        try:
            last_accessed = sys.argv[2]
            access_count = int(sys.argv[3])
            
            score = calculate_salience_score(last_accessed, access_count)
            recency = calculate_recency_weight(last_accessed)
            frequency = math.log(access_count + 1)
            
            print(f"Salience Score Calculation:")
            print(f"Last accessed: {last_accessed}")
            print(f"Access count: {access_count}")
            print(f"Recency weight: {round(recency, 4)}")
            print(f"Frequency weight: {round(frequency, 4)}")
            print(f"Final score: {round(score, 4)}")
        except ValueError:
            print("Error: access_count must be an integer")
    
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Cross-referencing / Backlinks System
Builds relationship graphs from existing items.json data
Enables "show everything connected to X" traversal
Auto-detects relationships from daily notes mentions
"""

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque

# Configurable workspace directory
WORKSPACE_DIR = Path(os.environ.get('WORKSPACE_DIR', os.getcwd()))
PATTERNS_FILE = WORKSPACE_DIR / "patterns.json"

def load_patterns():
    """Load relationship patterns from patterns.json"""
    try:
        with open(PATTERNS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": 1, "relationships": [], "behavioral_sequences": []}

def save_patterns(patterns):
    """Save patterns to patterns.json"""
    try:
        PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PATTERNS_FILE, 'w') as f:
            json.dump(patterns, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving patterns: {e}")
        return False

def extract_entity_info(entity_path):
    """Extract entity type and name from path"""
    parts = Path(entity_path).parts
    
    # Find the areas index
    try:
        areas_idx = parts.index('areas')
        entity_type = parts[areas_idx + 1]  # people, companies, etc.
        entity_name = parts[areas_idx + 2]  # specific entity name
        return f"{entity_type}/{entity_name}"
    except (ValueError, IndexError):
        return str(entity_path)

def find_all_entities():
    """Find all entities in the workspace"""
    entities = {}
    
    for items_file in WORKSPACE_DIR.rglob("items.json"):
        entity_key = extract_entity_info(items_file.parent)
        entities[entity_key] = str(items_file.parent)
    
    return entities

def detect_relationships_from_content():
    """Auto-detect relationships from items.json content and daily notes"""
    entities = find_all_entities()
    relationships = []
    
    # Build entity name lookup (for mention detection)
    entity_names = {}
    for entity_key in entities.keys():
        entity_type, entity_name = entity_key.split('/', 1)
        entity_names[entity_name.lower()] = entity_key
        # Also add variations without special chars
        clean_name = re.sub(r'[_-]', ' ', entity_name.lower())
        entity_names[clean_name] = entity_key
    
    print(f"Scanning for relationships among {len(entities)} entities...")
    
    # Scan items.json files for relationship patterns
    for entity_key, entity_path in entities.items():
        items_file = Path(entity_path) / "items.json"
        
        try:
            with open(items_file, 'r') as f:
                items = json.load(f)
            
            for item in items:
                fact = item.get('fact', '').lower()
                
                # Look for direct relationship indicators
                for relation_type in ['works_at', 'knows', 'uses', 'manages', 'leads', 'founded']:
                    if relation_type.replace('_', ' ') in fact:
                        # Try to extract the target entity
                        for other_entity_name, other_entity_key in entity_names.items():
                            if other_entity_name in fact and other_entity_key != entity_key:
                                relationships.append({
                                    'from': entity_key,
                                    'to': other_entity_key,
                                    'relation': relation_type,
                                    'since': item.get('timestamp', datetime.now().strftime('%Y-%m-%d')),
                                    'source': f"{items_file}#{item.get('id')}"
                                })
                
                # Look for mentions of other entities (general connection)
                mentioned_entities = []
                for other_entity_name, other_entity_key in entity_names.items():
                    if (other_entity_name in fact and 
                        other_entity_key != entity_key and 
                        len(other_entity_name) > 3):  # Skip very short names
                        mentioned_entities.append(other_entity_key)
                
                # Create "mentions" relationships
                for mentioned_entity in mentioned_entities:
                    relationships.append({
                        'from': entity_key,
                        'to': mentioned_entity,
                        'relation': 'mentions',
                        'since': item.get('timestamp', datetime.now().strftime('%Y-%m-%d')),
                        'source': f"{items_file}#{item.get('id')}"
                    })
                    
        except Exception as e:
            print(f"Error processing {items_file}: {e}")
            continue
    
    # Scan daily notes for entity mentions
    memory_dir = WORKSPACE_DIR / "memory"
    if memory_dir.exists():
        for note_file in memory_dir.glob("*.md"):
            try:
                with open(note_file, 'r') as f:
                    content = f.read().lower()
                
                # Find all entities mentioned in this note
                mentioned_in_note = []
                for entity_name, entity_key in entity_names.items():
                    if entity_name in content and len(entity_name) > 3:
                        mentioned_in_note.append(entity_key)
                
                # Create cross-relationships between co-mentioned entities
                for i, entity1 in enumerate(mentioned_in_note):
                    for entity2 in mentioned_in_note[i+1:]:
                        relationships.append({
                            'from': entity1,
                            'to': entity2,
                            'relation': 'co_mentioned',
                            'since': note_file.stem,  # Use date from filename
                            'source': str(note_file)
                        })
                        
            except Exception as e:
                print(f"Error processing {note_file}: {e}")
                continue
    
    # Deduplicate relationships
    unique_relationships = []
    seen = set()
    
    for rel in relationships:
        # Create a key for deduplication
        key = f"{rel['from']}#{rel['to']}#{rel['relation']}"
        if key not in seen:
            seen.add(key)
            unique_relationships.append(rel)
    
    print(f"Detected {len(unique_relationships)} unique relationships")
    return unique_relationships

def build_relationship_graph():
    """Build a directed graph from relationship data"""
    patterns = load_patterns()
    relationships = patterns.get('relationships', [])
    
    graph = defaultdict(list)
    reverse_graph = defaultdict(list)  # For finding inbound connections
    
    for rel in relationships:
        from_entity = rel['from']
        to_entity = rel['to']
        
        graph[from_entity].append({
            'target': to_entity,
            'relation': rel['relation'],
            'since': rel.get('since'),
            'source': rel.get('source')
        })
        
        reverse_graph[to_entity].append({
            'source': from_entity,
            'relation': rel['relation'],
            'since': rel.get('since'),
            'source_ref': rel.get('source')
        })
    
    return graph, reverse_graph

def traverse_connections(entity_key, max_depth=2, direction='both'):
    """Traverse and return all entities connected to the given entity"""
    graph, reverse_graph = build_relationship_graph()
    
    visited = set()
    connections = defaultdict(list)
    queue = deque([(entity_key, 0)])  # (entity, depth)
    
    while queue:
        current_entity, depth = queue.popleft()
        
        if current_entity in visited or depth > max_depth:
            continue
        
        visited.add(current_entity)
        
        # Add outbound connections
        if direction in ['both', 'out']:
            for connection in graph.get(current_entity, []):
                target = connection['target']
                connections[depth].append({
                    'from': current_entity,
                    'to': target,
                    'type': 'outbound',
                    **connection
                })
                
                if target not in visited:
                    queue.append((target, depth + 1))
        
        # Add inbound connections
        if direction in ['both', 'in']:
            for connection in reverse_graph.get(current_entity, []):
                source = connection['source']
                connections[depth].append({
                    'from': source,
                    'to': current_entity,
                    'type': 'inbound',
                    'relation': connection['relation'],
                    'since': connection.get('since'),
                    'source': connection.get('source_ref')
                })
                
                if source not in visited:
                    queue.append((source, depth + 1))
    
    return connections

def add_relationship(from_entity, to_entity, relation, since=None):
    """Add a new relationship to patterns.json"""
    patterns = load_patterns()
    
    if since is None:
        since = datetime.now().strftime('%Y-%m-%d')
    
    new_relationship = {
        'from': from_entity,
        'to': to_entity,
        'relation': relation,
        'since': since
    }
    
    # Check if relationship already exists
    for existing in patterns['relationships']:
        if (existing['from'] == from_entity and 
            existing['to'] == to_entity and 
            existing['relation'] == relation):
            print(f"Relationship already exists: {from_entity} -> {to_entity} ({relation})")
            return False
    
    patterns['relationships'].append(new_relationship)
    
    if save_patterns(patterns):
        print(f"Added relationship: {from_entity} -> {to_entity} ({relation})")
        return True
    else:
        print("Failed to save relationship")
        return False

def show_entity_connections(entity_key, max_depth=2):
    """Show all connections for an entity in a readable format"""
    connections = traverse_connections(entity_key, max_depth)
    
    if not any(connections.values()):
        return f"No connections found for {entity_key}"
    
    result = f"\nConnections for {entity_key}:\n"
    result += "=" * (len(entity_key) + 16) + "\n"
    
    for depth in sorted(connections.keys()):
        if connections[depth]:
            result += f"\nDepth {depth}:\n"
            result += "-" * 20 + "\n"
            
            for conn in connections[depth]:
                direction = "→" if conn['type'] == 'outbound' else "←"
                result += f"{conn['from']} {direction} {conn['to']} ({conn['relation']})\n"
                
                if conn.get('since'):
                    result += f"  Since: {conn['since']}\n"
                if conn.get('source'):
                    result += f"  Source: {conn['source']}\n"
    
    return result

def show_help():
    """Show usage information"""
    print(f"""
Cross-referencing / Backlinks System

WORKSPACE: {WORKSPACE_DIR}

USAGE:
    cross-ref.py scan                           # Auto-detect relationships from content
    cross-ref.py build                          # Rebuild relationship graph  
    cross-ref.py show <entity>                  # Show connections for entity
    cross-ref.py add <from> <to> <relation>     # Add relationship manually
    cross-ref.py stats                          # Show relationship statistics
    cross-ref.py list                           # List all entities
    cross-ref.py --help                         # Show this help

EXAMPLES:
    cross-ref.py show people/john
    cross-ref.py add people/john companies/acme works_at
    cross-ref.py scan

ENTITY FORMAT:
    type/name (e.g., people/john, companies/acme, projects/app)

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
""")

def show_stats():
    """Show relationship statistics"""
    patterns = load_patterns()
    relationships = patterns.get('relationships', [])
    
    if not relationships:
        print("No relationships found. Run 'scan' to detect relationships.")
        return
    
    # Count by relation type
    relation_counts = defaultdict(int)
    for rel in relationships:
        relation_counts[rel['relation']] += 1
    
    # Count by entity type
    entity_type_counts = defaultdict(int)
    for rel in relationships:
        from_type = rel['from'].split('/')[0]
        to_type = rel['to'].split('/')[0]
        entity_type_counts[f"{from_type} -> {to_type}"] += 1
    
    print(f"\nRelationship Statistics:")
    print("-" * 25)
    print(f"Total relationships: {len(relationships)}")
    
    print(f"\nBy relation type:")
    for relation, count in sorted(relation_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {relation}: {count}")
    
    print(f"\nBy entity type:")
    for entity_combo, count in sorted(entity_type_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {entity_combo}: {count}")

def list_entities():
    """List all entities in the workspace"""
    entities = find_all_entities()
    
    by_type = defaultdict(list)
    for entity_key in entities.keys():
        entity_type, entity_name = entity_key.split('/', 1)
        by_type[entity_type].append(entity_name)
    
    print(f"\nEntities by type:")
    print("-" * 20)
    for entity_type, names in sorted(by_type.items()):
        print(f"\n{entity_type.upper()} ({len(names)}):")
        for name in sorted(names):
            print(f"  {entity_type}/{name}")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == 'scan':
        relationships = detect_relationships_from_content()
        
        patterns = load_patterns()
        
        # Merge new relationships with existing ones
        existing_keys = set()
        for existing in patterns.get('relationships', []):
            key = f"{existing['from']}#{existing['to']}#{existing['relation']}"
            existing_keys.add(key)
        
        new_relationships = []
        for rel in relationships:
            key = f"{rel['from']}#{rel['to']}#{rel['relation']}"
            if key not in existing_keys:
                new_relationships.append(rel)
        
        patterns['relationships'].extend(new_relationships)
        
        if save_patterns(patterns):
            print(f"Added {len(new_relationships)} new relationships to patterns.json")
        else:
            print("Failed to save relationships")
    
    elif command in ['build', 'rebuild']:
        print("Rebuilding relationship graph...")
        graph, reverse_graph = build_relationship_graph()
        print(f"Graph built with {len(graph)} outbound and {len(reverse_graph)} inbound connections")
    
    elif command == 'show':
        if len(sys.argv) < 3:
            print("Usage: cross-ref.py show <entity>")
            return
        
        entity_key = sys.argv[2]
        max_depth = 2
        
        if '--depth' in sys.argv:
            try:
                depth_idx = sys.argv.index('--depth')
                max_depth = int(sys.argv[depth_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --depth value")
                return
        
        result = show_entity_connections(entity_key, max_depth)
        print(result)
    
    elif command == 'add':
        if len(sys.argv) < 5:
            print("Usage: cross-ref.py add <from> <to> <relation>")
            return
        
        from_entity = sys.argv[2]
        to_entity = sys.argv[3]
        relation = sys.argv[4]
        
        add_relationship(from_entity, to_entity, relation)
    
    elif command == 'stats':
        show_stats()
    
    elif command == 'list':
        list_entities()
    
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
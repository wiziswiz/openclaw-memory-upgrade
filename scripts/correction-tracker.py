#!/usr/bin/env python3
"""
Correction Learning System
Tracks patterns when user corrects behavior to prevent repeating mistakes
Schema: { id, pattern, correction, context, timestamp, appliedCount }
"""

import json
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path

# Configurable workspace directory
WORKSPACE_DIR = Path(os.environ.get('WORKSPACE_DIR', os.getcwd()))
CORRECTIONS_FILE = WORKSPACE_DIR / ".corrections.json"

def load_corrections():
    """Load existing corrections from file"""
    try:
        with open(CORRECTIONS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_corrections(corrections):
    """Save corrections to file"""
    try:
        CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CORRECTIONS_FILE, 'w') as f:
            json.dump(corrections, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving corrections: {e}")
        return False

def generate_correction_id(pattern, correction):
    """Generate unique ID for a correction based on pattern and correction"""
    content = f"{pattern.lower().strip()}:{correction.lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()[:8]

def add_correction(pattern, correction, context=None):
    """Add a new correction pattern"""
    corrections = load_corrections()
    
    # Check if similar correction already exists
    pattern_lower = pattern.lower().strip()
    correction_lower = correction.lower().strip()
    
    for existing in corrections:
        if (existing.get('pattern', '').lower().strip() == pattern_lower and
            existing.get('correction', '').lower().strip() == correction_lower):
            print(f"Similar correction already exists: {existing['id']}")
            return existing['id']
    
    # Create new correction
    correction_id = generate_correction_id(pattern, correction)
    
    new_correction = {
        'id': correction_id,
        'pattern': pattern.strip(),
        'correction': correction.strip(),
        'context': context.strip() if context else None,
        'timestamp': datetime.now().isoformat(),
        'appliedCount': 0,
        'lastApplied': None
    }
    
    corrections.append(new_correction)
    
    if save_corrections(corrections):
        print(f"Added correction: {correction_id}")
        return correction_id
    else:
        print("Failed to save correction")
        return None

def check_for_corrections(action_text):
    """Check if an action matches any known correction patterns"""
    corrections = load_corrections()
    
    if not corrections:
        return []
    
    action_lower = action_text.lower().strip()
    matching_corrections = []
    
    for correction in corrections:
        pattern = correction.get('pattern', '').lower().strip()
        
        # Simple keyword matching for patterns
        pattern_words = pattern.split()
        
        # Check if pattern matches the action
        if all(word in action_lower for word in pattern_words if len(word) > 2):
            matching_corrections.append(correction)
    
    return matching_corrections

def apply_correction(correction_id):
    """Mark a correction as applied (increment counter)"""
    corrections = load_corrections()
    
    for correction in corrections:
        if correction.get('id') == correction_id:
            correction['appliedCount'] = correction.get('appliedCount', 0) + 1
            correction['lastApplied'] = datetime.now().isoformat()
            
            if save_corrections(corrections):
                return True, f"Marked correction {correction_id} as applied (count: {correction['appliedCount']})"
            else:
                return False, "Failed to save correction update"
    
    return False, f"Correction {correction_id} not found"

def extract_correction_from_feedback(feedback_text, current_action=None):
    """Extract correction patterns from user feedback"""
    
    # Common correction patterns to look for
    correction_indicators = [
        (r"don't (.*?) instead (.*)", "negative_redirect"),
        (r"no,? (.*?) instead", "direct_correction"),
        (r"stop (.*?) and (.*)", "stop_start"),
        (r"instead of (.*?) do (.*)", "replacement"),
        (r"rather than (.*?) try (.*)", "alternative"),
        (r"avoid (.*?) when (.*)", "conditional_avoid"),
        (r"finish (.*?) before (.*)", "sequence_correction")
    ]
    
    feedback_lower = feedback_text.lower().strip()
    
    # Look for explicit correction patterns
    extracted_corrections = []
    
    # Simple heuristic extraction
    if "instead" in feedback_lower:
        if current_action:
            pattern = current_action.strip()
            correction = feedback_text.strip()
            extracted_corrections.append((pattern, correction))
    
    elif "don't" in feedback_lower and ("when" in feedback_lower or "during" in feedback_lower):
        pattern = current_action.strip() if current_action else "unspecified action"
        correction = feedback_text.strip()
        extracted_corrections.append((pattern, correction))
    
    elif "finish" in feedback_lower and "before" in feedback_lower:
        pattern = "starting new task without completing current"
        correction = feedback_text.strip()
        extracted_corrections.append((pattern, correction))
    
    return extracted_corrections

def show_correction_report():
    """Show detailed correction report"""
    corrections = load_corrections()
    
    if not corrections:
        return "No corrections recorded yet."
    
    # Sort by applied count (most applied first)
    corrections.sort(key=lambda x: x.get('appliedCount', 0), reverse=True)
    
    report = f"\nCorrection Learning Report\n"
    report += "=" * 30 + "\n"
    report += f"Total corrections: {len(corrections)}\n\n"
    
    for correction in corrections:
        applied_count = correction.get('appliedCount', 0)
        last_applied = correction.get('lastApplied', 'Never')
        
        if last_applied != 'Never':
            try:
                last_applied_date = datetime.fromisoformat(last_applied)
                last_applied = last_applied_date.strftime('%Y-%m-%d %H:%M')
            except:
                pass
        
        report += f"ID: {correction.get('id', 'N/A')}\n"
        report += f"Pattern: {correction.get('pattern', 'N/A')}\n"
        report += f"Correction: {correction.get('correction', 'N/A')}\n"
        
        if correction.get('context'):
            report += f"Context: {correction.get('context')}\n"
        
        report += f"Applied: {applied_count} times (last: {last_applied})\n"
        report += f"Created: {correction.get('timestamp', 'N/A')[:10]}\n"
        report += "-" * 50 + "\n\n"
    
    return report

def show_stats():
    """Show correction statistics"""
    corrections = load_corrections()
    
    if not corrections:
        print("No corrections recorded.")
        return
    
    total_corrections = len(corrections)
    applied_corrections = len([c for c in corrections if c.get('appliedCount', 0) > 0])
    total_applications = sum(c.get('appliedCount', 0) for c in corrections)
    
    # Most applied corrections
    most_applied = sorted(corrections, key=lambda x: x.get('appliedCount', 0), reverse=True)[:5]
    
    print(f"\nCorrection Statistics:")
    print("-" * 22)
    print(f"Total corrections: {total_corrections}")
    print(f"Applied corrections: {applied_corrections}")
    print(f"Total applications: {total_applications}")
    print(f"Average applications per correction: {total_applications / total_corrections:.1f}")
    
    if most_applied and most_applied[0].get('appliedCount', 0) > 0:
        print(f"\nMost Applied Corrections:")
        for i, correction in enumerate(most_applied, 1):
            count = correction.get('appliedCount', 0)
            if count > 0:
                print(f"{i}. {correction.get('pattern', 'N/A')[:40]}... ({count}x)")

def search_corrections(query):
    """Search corrections by pattern, correction, or context"""
    corrections = load_corrections()
    
    if not corrections:
        return []
    
    query_lower = query.lower().strip()
    matching = []
    
    for correction in corrections:
        pattern = correction.get('pattern', '').lower()
        correction_text = correction.get('correction', '').lower()
        context = correction.get('context', '').lower()
        
        if (query_lower in pattern or 
            query_lower in correction_text or 
            query_lower in context):
            matching.append(correction)
    
    return matching

def show_help():
    """Show usage information"""
    print(f"""
Correction Learning System

WORKSPACE: {WORKSPACE_DIR}

USAGE:
    correction-tracker.py add <pattern> <correction> [context]  # Add new correction
    correction-tracker.py check <action>                       # Check for matching corrections
    correction-tracker.py apply <correction-id>                # Mark correction as applied
    correction-tracker.py extract <feedback> [current-action]  # Extract from feedback
    correction-tracker.py list                                 # List all corrections
    correction-tracker.py report                               # Detailed correction report
    correction-tracker.py search <query>                       # Search corrections
    correction-tracker.py stats                                # Show statistics
    correction-tracker.py --help                               # Show this help

EXAMPLES:
    correction-tracker.py add "sending messages during build" "finish current task before switching"
    correction-tracker.py check "about to send DM to investor"
    correction-tracker.py apply abc123de
    correction-tracker.py extract "no, finish the memory build first" "sending YC DMs"

SCHEMA:
    Each correction has: id, pattern, correction, context, timestamp, appliedCount

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
""")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == 'add':
        if len(sys.argv) < 4:
            print("Usage: correction-tracker.py add <pattern> <correction> [context]")
            return
        
        pattern = sys.argv[2]
        correction = sys.argv[3]
        context = sys.argv[4] if len(sys.argv) > 4 else None
        
        correction_id = add_correction(pattern, correction, context)
        if correction_id:
            print(f"Correction added with ID: {correction_id}")
    
    elif command == 'check':
        if len(sys.argv) < 3:
            print("Usage: correction-tracker.py check <action>")
            return
        
        action = ' '.join(sys.argv[2:])
        matches = check_for_corrections(action)
        
        if not matches:
            print("No matching corrections found.")
            return
        
        print(f"Found {len(matches)} matching correction(s):")
        print("-" * 40)
        
        for match in matches:
            print(f"ID: {match.get('id')}")
            print(f"Pattern: {match.get('pattern')}")
            print(f"Correction: {match.get('correction')}")
            if match.get('context'):
                print(f"Context: {match.get('context')}")
            print(f"Applied: {match.get('appliedCount', 0)} times")
            print("-" * 40)
    
    elif command == 'apply':
        if len(sys.argv) < 3:
            print("Usage: correction-tracker.py apply <correction-id>")
            return
        
        correction_id = sys.argv[2]
        success, message = apply_correction(correction_id)
        print(message)
    
    elif command == 'extract':
        if len(sys.argv) < 3:
            print("Usage: correction-tracker.py extract <feedback> [current-action]")
            return
        
        feedback = sys.argv[2]
        current_action = sys.argv[3] if len(sys.argv) > 3 else None
        
        extracted = extract_correction_from_feedback(feedback, current_action)
        
        if not extracted:
            print("No corrections patterns detected in feedback.")
            return
        
        print(f"Extracted {len(extracted)} correction pattern(s):")
        for pattern, correction in extracted:
            print(f"Pattern: {pattern}")
            print(f"Correction: {correction}")
            
            # Optionally add them
            confirm = input("Add this correction? (y/n): ")
            if confirm.lower() == 'y':
                correction_id = add_correction(pattern, correction, f"Extracted from: {feedback}")
                if correction_id:
                    print(f"Added as {correction_id}")
            print()
    
    elif command == 'list':
        corrections = load_corrections()
        
        if not corrections:
            print("No corrections found.")
            return
        
        print(f"\nAll Corrections ({len(corrections)}):")
        print("-" * 25)
        
        for correction in corrections:
            print(f"{correction.get('id')}: {correction.get('pattern')}")
            print(f"  → {correction.get('correction')}")
            print(f"  Applied: {correction.get('appliedCount', 0)} times")
            print()
    
    elif command == 'report':
        report = show_correction_report()
        print(report)
    
    elif command == 'search':
        if len(sys.argv) < 3:
            print("Usage: correction-tracker.py search <query>")
            return
        
        query = ' '.join(sys.argv[2:])
        matches = search_corrections(query)
        
        if not matches:
            print(f"No corrections found matching: {query}")
            return
        
        print(f"Found {len(matches)} matching correction(s):")
        print("-" * 40)
        
        for match in matches:
            print(f"ID: {match.get('id')}")
            print(f"Pattern: {match.get('pattern')}")
            print(f"Correction: {match.get('correction')}")
            print(f"Applied: {match.get('appliedCount', 0)} times")
            print("-" * 40)
    
    elif command == 'stats':
        show_stats()
    
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Autonomous Follow-up Drafter
Reads pending-threads.json and drafts follow-ups for stale threads (>48h)
Does NOT send messages - only presents for approval
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Configurable workspace directory
WORKSPACE_DIR = Path(os.environ.get('WORKSPACE_DIR', os.getcwd()))
THREADS_FILE = WORKSPACE_DIR / "pending-threads.json"

def load_pending_threads():
    """Load pending threads from JSON file"""
    try:
        with open(THREADS_FILE, 'r') as f:
            data = json.load(f)
            # Handle both formats: direct array or nested with "threads" key
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "threads" in data:
                return data["threads"]
            else:
                return []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_pending_threads(threads):
    """Save updated threads back to JSON file"""
    try:
        # Try to read existing structure to preserve format
        try:
            with open(THREADS_FILE, 'r') as f:
                existing_data = json.load(f)
            if isinstance(existing_data, dict) and "threads" in existing_data:
                # Maintain nested structure
                existing_data["threads"] = threads
                data_to_save = existing_data
            else:
                # Use direct array format
                data_to_save = threads
        except:
            # Default to nested structure for new files
            data_to_save = {"version": 1, "threads": threads}
        
        THREADS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(THREADS_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving threads: {e}")
        return False

def is_stale(thread, hours=48):
    """Check if a thread is stale (older than specified hours)"""
    try:
        opened_date = datetime.fromisoformat(thread['opened'])
        now = datetime.now()
        return (now - opened_date).total_seconds() > (hours * 3600)
    except (ValueError, KeyError):
        return False

def get_days_since_opened(thread):
    """Get number of days since thread was opened"""
    try:
        opened_date = datetime.fromisoformat(thread['opened'])
        now = datetime.now()
        return (now - opened_date).days
    except (ValueError, KeyError):
        return 0

def draft_followup_message(thread):
    """Draft a follow-up message for a stale thread"""
    
    subject = thread.get('subject', 'Previous conversation')
    contact = thread.get('contact', 'there')
    notes = thread.get('notes', '')
    days_since = get_days_since_opened(thread)
    
    # Different templates based on thread context and age
    templates = {
        'initial_outreach': [
            f"Hi {contact}, just circling back on {subject}. Would love to connect when you have a moment.",
            f"Hey {contact}, following up on my message about {subject}. Any thoughts?",
            f"Hi {contact}, wanted to check in about {subject}. Happy to jump on a quick call if easier."
        ],
        'meeting_request': [
            f"Hi {contact}, wanted to follow up on scheduling time to discuss {subject}. Any availability this week?",
            f"Hey {contact}, checking in about our potential meeting re: {subject}. What works for your calendar?",
            f"Hi {contact}, following up to see if we can find time to connect about {subject}."
        ],
        'information_request': [
            f"Hi {contact}, following up on {subject}. Any updates you can share?",
            f"Hey {contact}, circling back to see if you have any info on {subject}.",
            f"Hi {contact}, wanted to check in about {subject}. Any progress to report?"
        ],
        'business_proposal': [
            f"Hi {contact}, wanted to follow up on our {subject} discussion. Any questions I can answer?",
            f"Hey {contact}, checking in about {subject}. Happy to provide more details if helpful.",
            f"Hi {contact}, following up on {subject}. Would love to hear your thoughts when you have a chance."
        ],
        'general': [
            f"Hi {contact}, wanted to follow up on our conversation about {subject}.",
            f"Hey {contact}, circling back on {subject}. Any updates?",
            f"Hi {contact}, checking in about {subject}. Let me know your thoughts when convenient."
        ]
    }
    
    # Determine message type based on subject and notes
    message_type = 'general'
    subject_lower = subject.lower()
    notes_lower = notes.lower()
    
    if any(word in subject_lower or word in notes_lower for word in ['meeting', 'call', 'schedule', 'calendar']):
        message_type = 'meeting_request'
    elif any(word in subject_lower or word in notes_lower for word in ['info', 'update', 'status', 'progress']):
        message_type = 'information_request'
    elif any(word in subject_lower or word in notes_lower for word in ['proposal', 'partnership', 'business', 'deal']):
        message_type = 'business_proposal'
    elif 'outreach' in notes_lower or 'first contact' in notes_lower:
        message_type = 'initial_outreach'
    
    # Select template based on days elapsed
    templates_for_type = templates[message_type]
    
    if days_since <= 3:
        template_index = 0  # Gentle first follow-up
    elif days_since <= 7:
        template_index = 1  # More direct second follow-up  
    else:
        template_index = 2  # Final attempt or more casual
    
    base_message = templates_for_type[min(template_index, len(templates_for_type) - 1)]
    
    # Add context if available in notes
    if notes and len(notes.strip()) > 0:
        context_note = f"\n\n(Context: {notes})"
    else:
        context_note = ""
    
    # Add urgency indication for very stale threads
    urgency_note = ""
    if days_since > 14:
        urgency_note = "\n\n[Note: This thread is quite stale - consider if follow-up is still relevant]"
    elif days_since > 7:
        urgency_note = "\n\n[Note: This is a second+ follow-up attempt]"
    
    return {
        'draft_message': base_message,
        'context_notes': context_note,
        'urgency_indicator': urgency_note,
        'suggested_timing': 'Send within next 24 hours' if days_since < 7 else 'Consider if still relevant',
        'message_type': message_type,
        'days_stale': days_since
    }

def get_stale_threads(hours=48):
    """Get all threads that are stale and need follow-up"""
    threads = load_pending_threads()
    
    stale_threads = []
    for thread in threads:
        if thread.get('status') == 'open' and is_stale(thread, hours):
            stale_threads.append(thread)
    
    return stale_threads

def generate_followup_report():
    """Generate a comprehensive follow-up report"""
    stale_threads = get_stale_threads()
    
    if not stale_threads:
        return "No stale threads requiring follow-up at this time."
    
    report = f"\nAutonomous Follow-up Report\n"
    report += "=" * 30 + "\n"
    report += f"Found {len(stale_threads)} stale threads requiring attention:\n\n"
    
    # Sort by staleness (oldest first)
    stale_threads.sort(key=lambda t: datetime.fromisoformat(t['opened']))
    
    for i, thread in enumerate(stale_threads, 1):
        days_stale = get_days_since_opened(thread)
        
        report += f"{i}. {thread.get('subject', 'Untitled thread')}\n"
        report += f"   Contact: {thread.get('contact', 'Unknown')}\n"
        report += f"   Channel: {thread.get('channel', 'Unknown')}\n" 
        report += f"   Opened: {thread.get('opened', 'Unknown')} ({days_stale} days ago)\n"
        
        if thread.get('notes'):
            report += f"   Notes: {thread.get('notes')}\n"
        
        # Generate draft follow-up
        draft = draft_followup_message(thread)
        
        report += f"\n   SUGGESTED FOLLOW-UP:\n"
        report += f"   Channel: {thread.get('channel', 'email')}\n"
        report += f"   Recipient: {thread.get('contact')}\n"
        report += f"   Message: {draft['draft_message']}\n"
        
        if draft['urgency_indicator']:
            report += f"   {draft['urgency_indicator'].strip()}\n"
        
        report += f"   Timing: {draft['suggested_timing']}\n"
        report += "\n" + "-" * 50 + "\n\n"
    
    return report

def mark_thread_followed_up(thread_id):
    """Mark a thread as having been followed up"""
    threads = load_pending_threads()
    
    for thread in threads:
        if thread.get('id') == thread_id:
            thread['status'] = 'followed_up'
            thread['lastCheck'] = datetime.now().isoformat()
            break
    
    return save_pending_threads(threads)

def show_help():
    """Show usage information"""
    print(f"""
Autonomous Follow-up Drafter

WORKSPACE: {WORKSPACE_DIR}

USAGE:
    auto-followup.py report                     # Generate follow-up report
    auto-followup.py list [--hours N]           # List stale threads
    auto-followup.py draft <thread-id>          # Draft follow-up for specific thread
    auto-followup.py mark <thread-id>           # Mark thread as followed up
    auto-followup.py stats                      # Show thread statistics
    auto-followup.py --help                     # Show this help

EXAMPLES:
    auto-followup.py report
    auto-followup.py list --hours 72
    auto-followup.py draft thread-123
    auto-followup.py mark thread-123

NOTES:
    - Reads from {THREADS_FILE}
    - Only suggests follow-ups, never sends messages
    - Considers threads >48h old as stale by default

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
""")

def show_stats():
    """Show thread statistics"""
    threads = load_pending_threads()
    
    if not threads:
        print("No pending threads found.")
        return
    
    total_threads = len(threads)
    open_threads = len([t for t in threads if t.get('status') == 'open'])
    stale_threads = len(get_stale_threads())
    
    # Age distribution
    age_buckets = {'<24h': 0, '1-3d': 0, '3-7d': 0, '7-14d': 0, '>14d': 0}
    
    for thread in threads:
        if thread.get('status') == 'open':
            days = get_days_since_opened(thread)
            if days < 1:
                age_buckets['<24h'] += 1
            elif days <= 3:
                age_buckets['1-3d'] += 1
            elif days <= 7:
                age_buckets['3-7d'] += 1
            elif days <= 14:
                age_buckets['7-14d'] += 1
            else:
                age_buckets['>14d'] += 1
    
    print(f"\nThread Statistics:")
    print("-" * 20)
    print(f"Total threads: {total_threads}")
    print(f"Open threads: {open_threads}")
    print(f"Stale threads (>48h): {stale_threads}")
    
    print(f"\nAge distribution (open threads):")
    for age_range, count in age_buckets.items():
        print(f"  {age_range}: {count}")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == 'report':
        report = generate_followup_report()
        print(report)
    
    elif command == 'list':
        hours = 48
        if '--hours' in sys.argv:
            try:
                hours_idx = sys.argv.index('--hours')
                hours = int(sys.argv[hours_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --hours value")
                return
        
        stale_threads = get_stale_threads(hours)
        
        if not stale_threads:
            print(f"No threads stale for more than {hours} hours.")
            return
        
        print(f"\nStale threads (>{hours}h):")
        print("-" * 25)
        
        for thread in stale_threads:
            days = get_days_since_opened(thread)
            print(f"{thread.get('id', 'N/A')}: {thread.get('subject', 'Untitled')} ({days}d old)")
            print(f"  Contact: {thread.get('contact', 'Unknown')} via {thread.get('channel', 'Unknown')}")
            if thread.get('notes'):
                print(f"  Notes: {thread.get('notes')}")
            print()
    
    elif command == 'draft':
        if len(sys.argv) < 3:
            print("Usage: auto-followup.py draft <thread-id>")
            return
        
        thread_id = sys.argv[2]
        threads = load_pending_threads()
        
        target_thread = None
        for thread in threads:
            if thread.get('id') == thread_id:
                target_thread = thread
                break
        
        if not target_thread:
            print(f"Thread {thread_id} not found")
            return
        
        draft = draft_followup_message(target_thread)
        days = get_days_since_opened(target_thread)
        
        print(f"\nDraft Follow-up for: {target_thread.get('subject', 'Untitled')}")
        print(f"Contact: {target_thread.get('contact', 'Unknown')}")
        print(f"Channel: {target_thread.get('channel', 'Unknown')}")
        print(f"Thread age: {days} days")
        print(f"Message type: {draft['message_type']}")
        print("-" * 40)
        print(f"\nSUGGESTED MESSAGE:")
        print(f"{draft['draft_message']}")
        print(f"\nTiming: {draft['suggested_timing']}")
        
        if draft['urgency_indicator']:
            print(draft['urgency_indicator'])
    
    elif command == 'mark':
        if len(sys.argv) < 3:
            print("Usage: auto-followup.py mark <thread-id>")
            return
        
        thread_id = sys.argv[2]
        if mark_thread_followed_up(thread_id):
            print(f"Marked thread {thread_id} as followed up")
        else:
            print(f"Failed to mark thread {thread_id}")
    
    elif command == 'stats':
        show_stats()
    
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
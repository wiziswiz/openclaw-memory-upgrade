#!/usr/bin/env python3
"""
Tool Performance Tracker - Logs and analyzes tool call performance
Tracks: tool, timestamp, success, durationMs, errorType
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median
from collections import defaultdict

# Configurable workspace directory
WORKSPACE_DIR = Path(os.environ.get('WORKSPACE_DIR', os.getcwd()))
PERF_LOG_FILE = WORKSPACE_DIR / ".tool-perf.json"

def load_perf_log():
    """Load existing performance log"""
    try:
        with open(PERF_LOG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_perf_log(log_data):
    """Save performance log to disk"""
    try:
        PERF_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PERF_LOG_FILE, 'w') as f:
            json.dump(log_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving performance log: {e}")
        return False

def log_tool_call(tool_name, success=True, duration_ms=None, error_type=None, details=None):
    """Log a tool call performance record"""
    log_data = load_perf_log()
    
    record = {
        'tool': tool_name,
        'timestamp': datetime.now().isoformat(),
        'success': success,
        'durationMs': duration_ms,
        'errorType': error_type,
        'details': details
    }
    
    log_data.append(record)
    
    # Keep only last 10,000 records to prevent file bloat
    if len(log_data) > 10000:
        log_data = log_data[-10000:]
    
    save_perf_log(log_data)
    return record

def get_tool_stats(tool_name=None, days=7):
    """Get performance statistics for a tool or all tools"""
    log_data = load_perf_log()
    
    # Filter by time window
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_data = [
        record for record in log_data
        if datetime.fromisoformat(record['timestamp']) >= cutoff_date
    ]
    
    # Filter by tool if specified
    if tool_name:
        recent_data = [record for record in recent_data if record['tool'] == tool_name]
    
    if not recent_data:
        return None
    
    # Calculate statistics
    total_calls = len(recent_data)
    successful_calls = len([r for r in recent_data if r['success']])
    success_rate = successful_calls / total_calls if total_calls > 0 else 0
    
    # Duration statistics (only for successful calls with duration data)
    durations = [r['durationMs'] for r in recent_data if r['success'] and r.get('durationMs')]
    
    duration_stats = {}
    if durations:
        duration_stats = {
            'mean': round(mean(durations), 2),
            'median': round(median(durations), 2),
            'min': min(durations),
            'max': max(durations)
        }
    
    # Error analysis
    error_counts = defaultdict(int)
    for record in recent_data:
        if not record['success'] and record.get('errorType'):
            error_counts[record['errorType']] += 1
    
    return {
        'tool': tool_name or 'ALL_TOOLS',
        'period_days': days,
        'total_calls': total_calls,
        'successful_calls': successful_calls,
        'success_rate': round(success_rate * 100, 1),
        'duration_stats': duration_stats,
        'error_types': dict(error_counts),
        'most_common_error': max(error_counts.items(), key=lambda x: x[1])[0] if error_counts else None
    }

def get_top_tools_by_usage(days=7):
    """Get most frequently used tools"""
    log_data = load_perf_log()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_data = [
        record for record in log_data
        if datetime.fromisoformat(record['timestamp']) >= cutoff_date
    ]
    
    tool_counts = defaultdict(int)
    for record in recent_data:
        tool_counts[record['tool']] += 1
    
    return sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)

def get_slowest_tools(days=7):
    """Get tools with highest average duration"""
    log_data = load_perf_log()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_data = [
        record for record in log_data
        if datetime.fromisoformat(record['timestamp']) >= cutoff_date
        and record['success']
        and record.get('durationMs')
    ]
    
    tool_durations = defaultdict(list)
    for record in recent_data:
        tool_durations[record['tool']].append(record['durationMs'])
    
    tool_avg_durations = []
    for tool, durations in tool_durations.items():
        if len(durations) >= 3:  # Only include tools with at least 3 data points
            avg_duration = mean(durations)
            tool_avg_durations.append((tool, round(avg_duration, 2), len(durations)))
    
    return sorted(tool_avg_durations, key=lambda x: x[1], reverse=True)

def get_least_reliable_tools(days=7):
    """Get tools with lowest success rates"""
    log_data = load_perf_log()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_data = [
        record for record in log_data
        if datetime.fromisoformat(record['timestamp']) >= cutoff_date
    ]
    
    tool_stats = defaultdict(lambda: {'total': 0, 'success': 0})
    for record in recent_data:
        tool_stats[record['tool']]['total'] += 1
        if record['success']:
            tool_stats[record['tool']]['success'] += 1
    
    tool_reliability = []
    for tool, stats in tool_stats.items():
        if stats['total'] >= 5:  # Only include tools with at least 5 calls
            success_rate = stats['success'] / stats['total']
            tool_reliability.append((tool, round(success_rate * 100, 1), stats['total']))
    
    return sorted(tool_reliability, key=lambda x: x[1])

def generate_daily_summary():
    """Generate a daily performance summary"""
    today = datetime.now().strftime('%Y-%m-%d')
    stats_24h = get_tool_stats(days=1)
    
    if not stats_24h:
        return "No tool calls in the last 24 hours"
    
    top_tools = get_top_tools_by_usage(days=1)[:5]
    slowest_tools = get_slowest_tools(days=1)[:3]
    unreliable_tools = get_least_reliable_tools(days=1)[:3]
    
    summary = f"""
Daily Tool Performance Summary - {today}
{'='*50}

OVERVIEW:
  Total calls: {stats_24h['total_calls']}
  Success rate: {stats_24h['success_rate']}%
  
TOP TOOLS (by usage):
"""
    
    for tool, count in top_tools:
        summary += f"  {tool}: {count} calls\n"
    
    if slowest_tools:
        summary += f"\nSLOWEST TOOLS (avg duration):\n"
        for tool, avg_ms, count in slowest_tools:
            summary += f"  {tool}: {avg_ms}ms (from {count} calls)\n"
    
    if unreliable_tools:
        summary += f"\nLEAST RELIABLE TOOLS:\n"
        for tool, success_rate, total in unreliable_tools:
            summary += f"  {tool}: {success_rate}% success (from {total} calls)\n"
    
    return summary

def show_help():
    """Show usage information"""
    print(f"""
Tool Performance Tracker

WORKSPACE: {WORKSPACE_DIR}

USAGE:
    tool-perf.py log <tool> [--success|--fail] [--duration <ms>] [--error <type>] [--details <text>]
    tool-perf.py stats [tool-name] [--days N]    # Show performance statistics
    tool-perf.py top [--days N]                  # Show most used tools
    tool-perf.py slow [--days N]                 # Show slowest tools
    tool-perf.py unreliable [--days N]           # Show least reliable tools
    tool-perf.py summary                         # Generate daily summary
    tool-perf.py clean [--days N]                # Remove old records
    tool-perf.py --help                          # Show this help

EXAMPLES:
    tool-perf.py log web_search --success --duration 1500
    tool-perf.py log gmail_send --fail --error timeout
    tool-perf.py stats web_search --days 30
    tool-perf.py top --days 7

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
""")

def clean_old_records(days=30):
    """Remove records older than specified days"""
    log_data = load_perf_log()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_data = [
        record for record in log_data
        if datetime.fromisoformat(record['timestamp']) >= cutoff_date
    ]
    
    removed_count = len(log_data) - len(filtered_data)
    save_perf_log(filtered_data)
    
    return removed_count

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == 'log':
        if len(sys.argv) < 3:
            print("Usage: tool-perf.py log <tool> [--success|--fail] [--duration <ms>] [--error <type>]")
            return
        
        tool_name = sys.argv[2]
        success = True
        duration_ms = None
        error_type = None
        details = None
        
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == '--success':
                success = True
            elif sys.argv[i] == '--fail':
                success = False
            elif sys.argv[i] == '--duration' and i + 1 < len(sys.argv):
                try:
                    duration_ms = int(sys.argv[i + 1])
                    i += 1
                except ValueError:
                    print(f"Invalid duration: {sys.argv[i + 1]}")
                    return
            elif sys.argv[i] == '--error' and i + 1 < len(sys.argv):
                error_type = sys.argv[i + 1]
                i += 1
            elif sys.argv[i] == '--details' and i + 1 < len(sys.argv):
                details = sys.argv[i + 1]
                i += 1
            i += 1
        
        record = log_tool_call(tool_name, success, duration_ms, error_type, details)
        print(f"Logged: {record['tool']} ({'success' if record['success'] else 'fail'})")
    
    elif command == 'stats':
        tool_name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
        days = 7
        
        if '--days' in sys.argv:
            try:
                days_idx = sys.argv.index('--days')
                days = int(sys.argv[days_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --days value")
                return
        
        stats = get_tool_stats(tool_name, days)
        if not stats:
            print(f"No data found for {tool_name or 'any tools'} in the last {days} days")
            return
        
        print(f"\nTool Performance Statistics: {stats['tool']} ({days} days)")
        print("-" * 50)
        print(f"Total calls: {stats['total_calls']}")
        print(f"Successful calls: {stats['successful_calls']}")
        print(f"Success rate: {stats['success_rate']}%")
        
        if stats['duration_stats']:
            print(f"\nDuration statistics (ms):")
            for stat, value in stats['duration_stats'].items():
                print(f"  {stat}: {value}")
        
        if stats['error_types']:
            print(f"\nError types:")
            for error, count in stats['error_types'].items():
                print(f"  {error}: {count}")
    
    elif command == 'top':
        days = 7
        if '--days' in sys.argv:
            try:
                days_idx = sys.argv.index('--days')
                days = int(sys.argv[days_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --days value")
                return
        
        top_tools = get_top_tools_by_usage(days)
        print(f"\nMost Used Tools ({days} days):")
        print("-" * 30)
        for i, (tool, count) in enumerate(top_tools[:10], 1):
            print(f"{i:2d}. {tool}: {count} calls")
    
    elif command == 'slow':
        days = 7
        if '--days' in sys.argv:
            try:
                days_idx = sys.argv.index('--days')
                days = int(sys.argv[days_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --days value")
                return
        
        slow_tools = get_slowest_tools(days)
        print(f"\nSlowest Tools ({days} days):")
        print("-" * 30)
        for tool, avg_ms, count in slow_tools[:10]:
            print(f"{tool}: {avg_ms}ms avg (from {count} calls)")
    
    elif command == 'unreliable':
        days = 7
        if '--days' in sys.argv:
            try:
                days_idx = sys.argv.index('--days')
                days = int(sys.argv[days_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --days value")
                return
        
        unreliable = get_least_reliable_tools(days)
        print(f"\nLeast Reliable Tools ({days} days):")
        print("-" * 35)
        for tool, success_rate, total in unreliable[:10]:
            print(f"{tool}: {success_rate}% success (from {total} calls)")
    
    elif command == 'summary':
        summary = generate_daily_summary()
        print(summary)
    
    elif command == 'clean':
        days = 30
        if '--days' in sys.argv:
            try:
                days_idx = sys.argv.index('--days')
                days = int(sys.argv[days_idx + 1])
            except (IndexError, ValueError):
                print("Invalid --days value")
                return
        
        removed = clean_old_records(days)
        print(f"Removed {removed} records older than {days} days")
    
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
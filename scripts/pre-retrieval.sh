#!/bin/bash
# Pre-retrieval Decision Module - Determines if queries need memory search
# Returns: "search" or "skip" based on query classification

# Configurable workspace directory
WORKSPACE_DIR="${WORKSPACE_DIR:-$(pwd)}"

show_help() {
    cat << 'EOF'
Pre-retrieval Decision Module

USAGE:
    pre-retrieval.sh <query>           # Classify single query
    pre-retrieval.sh --patterns        # Show skip patterns  
    pre-retrieval.sh --add-pattern <pattern> # Add new skip pattern
    pre-retrieval.sh --test           # Run test suite
    pre-retrieval.sh --help           # Show this help

OUTPUT:
    search    Query needs memory context
    skip      Query can be answered without memory

EXAMPLES:
    pre-retrieval.sh "what's the weather"     # -> skip
    pre-retrieval.sh "tell me about John"     # -> search
    pre-retrieval.sh "what time is it"        # -> skip
    pre-retrieval.sh "how's the project"      # -> search

ENVIRONMENT:
    WORKSPACE_DIR   Set custom workspace (default: current directory)
EOF
}

# File to store skip patterns
PATTERNS_FILE="$WORKSPACE_DIR/.pre-retrieval-patterns.txt"

# Default skip patterns (one per line)
init_patterns() {
    if [[ ! -f "$PATTERNS_FILE" ]]; then
        mkdir -p "$(dirname "$PATTERNS_FILE")"
        cat > "$PATTERNS_FILE" << 'EOF'
# Weather and time queries
^what'?s the weather
^what time is it
^current time
^what day is
^what date is

# Math and calculations
^calculate
^what is \d+
^\d+[\+\-\*/]\d+
^convert \d+
^how many (days|hours|minutes)

# Greetings and pleasantries  
^hi\b
^hello\b
^hey\b
^good (morning|afternoon|evening)
^how are you
^thanks?\b
^thank you

# Single tool commands (no context needed)
^check crypto
^show calendar
^list files
^run tests?
^git status
^git 
^weather
^time
^date

# Simple facts that don't need personal context
^what is [A-Z][a-z]+\b
^define \w+
^how do you
^what does \w+ mean
^explain \w+

# Update/meeting queries that need context
# (These are moved to ensure they DON'T skip)

# System/technical queries
^error:
^failed to
^permission denied
^command not found
^install
^update
^version

# Very short queries (likely simple)
^yes\b
^no\b
^ok\b
^sure\b
^done\b
^cancel
^stop
EOF
    fi
}

# Check if query matches skip patterns
should_skip() {
    local query="$1"
    local query_lower=$(echo "$query" | tr '[:upper:]' '[:lower:]')
    
    # Check for context-requiring terms first (before short query logic)
    # But exclude simple factual questions and git commands
    if [[ "$query_lower" =~ ^git ]]; then
        echo "skip"
        return
    fi
    
    if [[ "$query_lower" =~ ^what.is.[A-Za-z]+$ ]]; then
        echo "skip"
        return
    fi
    
    if [[ "$query_lower" =~ update.me|tell.me.about|how.is|how\'s|meeting.*project|project.*deal|going ]]; then
        echo "search"
        return
    fi
    
    # Very short queries (1-2 words) usually don't need context
    local word_count=$(echo "$query" | wc -w | tr -d ' ')
    if [[ $word_count -le 2 ]] && [[ ${#query} -lt 15 ]]; then
        # Exception: names or specific terms that might need context
        if [[ "$query_lower" =~ john|sarah|project|meeting|call|update|status|how ]]; then
            echo "search"
            return
        fi
        echo "skip"
        return
    fi
    
    # Check against patterns file
    while IFS= read -r pattern || [[ -n "$pattern" ]]; do
        # Skip comments and empty lines
        [[ "$pattern" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${pattern// }" ]] && continue
        
        # Remove leading/trailing whitespace
        pattern=$(echo "$pattern" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        
        if [[ "$query_lower" =~ $pattern ]]; then
            echo "skip"
            return
        fi
    done < "$PATTERNS_FILE"
    
    # Default to search if no patterns match
    echo "search"
}

# Add new skip pattern
add_pattern() {
    local pattern="$1"
    if [[ -z "$pattern" ]]; then
        echo "Error: Pattern cannot be empty"
        exit 1
    fi
    
    echo "$pattern" >> "$PATTERNS_FILE"
    echo "Added pattern: $pattern"
}

# Show current patterns
show_patterns() {
    echo "Current skip patterns:"
    echo "====================="
    echo "Patterns file: $PATTERNS_FILE"
    echo
    if [[ -f "$PATTERNS_FILE" ]]; then
        cat "$PATTERNS_FILE"
    else
        echo "No patterns file found. Run with a query first to initialize."
    fi
}

# Run test suite
run_tests() {
    echo "Running pre-retrieval test suite..."
    echo "==================================="
    
    # Test cases: query -> expected_result
    local tests=(
        "what's the weather|skip"
        "what time is it|skip"
        "hi there|skip"
        "calculate 2+2|skip"
        "tell me about John|search"
        "how's the project going|search"
        "update me on the meeting|search"
        "what is Python|skip"
        "yes|skip"
        "how is Sarah doing|search"
        "git status|skip"
        "check crypto|skip"
        "what happened with the deal|search"
        "error: command not found|skip"
    )
    
    local passed=0
    local failed=0
    
    for test in "${tests[@]}"; do
        IFS='|' read -r query expected <<< "$test"
        result=$(should_skip "$query")
        
        if [[ "$result" == "$expected" ]]; then
            echo "✓ PASS: '$query' -> $result"
            ((passed++))
        else
            echo "✗ FAIL: '$query' -> $result (expected $expected)"
            ((failed++))
        fi
    done
    
    echo
    echo "Results: $passed passed, $failed failed"
    echo "Workspace: $WORKSPACE_DIR"
    echo "Patterns file: $PATTERNS_FILE"
    
    if [[ $failed -gt 0 ]]; then
        exit 1
    fi
}

# Main logic
main() {
    # Initialize patterns if needed
    init_patterns
    
    case "$1" in
        --help|-h)
            show_help
            ;;
        --patterns)
            show_patterns
            ;;
        --add-pattern)
            shift
            add_pattern "$*"
            ;;
        --test)
            run_tests
            ;;
        "")
            echo "Error: Please provide a query to classify"
            echo "Use --help for usage information"
            exit 1
            ;;
        *)
            # Classify the query
            should_skip "$*"
            ;;
    esac
}

main "$@"
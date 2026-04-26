#!/bin/bash

# Load API keys
export OPENROUTER_API_KEY=$(powershell.exe -Command "[System.Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY', 'User')" | tr -d '\r\n')
export GROQ_API_KEY=$(powershell.exe -Command "[System.Environment]::GetEnvironmentVariable('GROQ_API_KEY', 'User')" | tr -d '\r\n')
export PYTHONUTF8=1
export LITELLM_LOG=ERROR

# Go to OpenJarvis folder
cd ~/OpenJarvis

# Print welcome banner
echo "================================================"
echo "  Welcome to OpenJarvis AI Assistant"
echo "  Model: Free AI via OpenRouter"
echo "================================================"
echo ""
echo "  Type your question and press Enter."
echo "  Example:  What is the capital of France?"
echo "  Type 'exit' to close."
echo ""

# Simple interactive loop
while true; do
    read -p "You: " question
    if [ "$question" = "exit" ] || [ "$question" = "quit" ]; then
        echo "Goodbye!"
        break
    fi
    if [ -z "$question" ]; then
        continue
    fi
    echo ""
    echo "Jarvis: (thinking, please wait...)"

    # Run jarvis and capture response
    response=$(uv run jarvis ask "$question" 2>&1)

    # Clear the "thinking" line and print response
    echo -e "\033[1A\033[2K"
    echo "Jarvis: $response"
    echo ""
done

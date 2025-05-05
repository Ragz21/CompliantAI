#!/bin/bash

echo "🧠 Starting Compliant AI Application..."

# (Optional) Wait for Ollama to be ready — safer if inference happens immediately
echo "⏳ Waiting for Ollama to be ready..."
until curl -s http://ollama:11434/api/tags > /dev/null; do
  echo "🚧 Ollama not yet available, retrying in 2s..."
  sleep 2
done

echo "✅ Ollama is ready!"

# Start the web server
exec gunicorn -k gthread -w 4 -b 0.0.0.0:5001 website.index:app

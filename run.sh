#!/bin/bash

pip install -r requirements.txt

ollama pull llama3:8b
ollama pull nomic-embed-text

ollama serve &

# python main.py
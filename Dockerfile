# Base image containing Ollama
FROM ollama/ollama:latest

# Install Python and basic tools
USER root
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv build-essential git && \
    rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy all project files
COPY . /app

# Install Python dependencies (allow system packages – required on Ubuntu 24.04)
RUN pip3 install --break-system-packages -r requirements.txt

# Environment variables so your app talks to Ollama INSIDE container
ENV OLLAMA_URL=http://127.0.0.1:11434/api/generate
ENV OLLAMA_MODEL=gemma3:1b

# Pre-pull the model (optional but recommended)
RUN ollama pull gemma3:1b || true

# Expose Streamlit port
EXPOSE 8501

# Start Ollama server + Streamlit app
CMD sh -c "\
    ollama serve --address 0.0.0.0 --port 11434 & \
    sleep 5 && \
    streamlit run app/main.py --server.port 8501 --server.address 0.0.0.0 \
"

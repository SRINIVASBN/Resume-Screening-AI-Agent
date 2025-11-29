# Use official Ollama image so the LLM server is inside the container
FROM ollama/ollama:latest

# We will run things as root to install Python
USER root

# Install Python + build tools
RUN apt-get update && apt-get install -y \
    python3 python3-pip build-essential git && \
    rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy all project files into the image
COPY . /app

# Upgrade pip and install Python dependencies
RUN python3 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt

# Make sure your app can find Ollama inside the container
ENV OLLAMA_URL=http://127.0.0.1:11434/api/generate
ENV OLLAMA_MODEL=gemma3:1b

# Pre-pull the model
RUN ollama pull gemma3:1b || true

# Expose default Streamlit port
EXPOSE 8501

# Start Ollama + Streamlit
CMD sh -c "\
    ollama serve --address 0.0.0.0 --port 11434 & \
    sleep 5 && \
    streamlit run app/main.py --server.port \$PORT --server.address 0.0.0.0 \
"

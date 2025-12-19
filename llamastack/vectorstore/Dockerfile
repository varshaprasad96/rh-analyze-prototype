FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the setup script
COPY setup-vectorstore.py .

# Run the setup script
ENTRYPOINT ["python3", "setup-vectorstore.py"]


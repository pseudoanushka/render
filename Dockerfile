FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the remaining application files into the container
COPY . .

# Expose the default port (Railway provides the PORT environment variable)
EXPOSE $PORT

# Command to run the application using hypercorn/uvicorn. 
# We use shell mode for CMD to ensure the $PORT environment variable supplied by Railway is parsed correctly.
CMD sh -c "uvicorn 03_04_render:app --host 0.0.0.0 --port ${PORT:-8000}"

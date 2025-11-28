# Use a slim Python base image for smaller size
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to optimize Docker caching
COPY requirements.txt /app/

# Install dependencies, ensuring we install the production dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# The application runs on port 8000
EXPOSE 8000

# Command to run the application using Uvicorn (ensuring it runs with 0.0.0.0 host)
CMD ["uvicorn", "main:app_fastapi", "--host", "0.0.0.0", "--port", "8000"]
# Use the official Python base image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app_andes_api

# Copy the Flask application code into the container
COPY ./my-flask-app /app_andes_api

# Copy the Flask application code into the container
COPY ./my-flask-app /aux_function

# Copy the Andes directory from the parent directory into the container
COPY ../andes /app_andes_api/andes  

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install your modified Andes package (if it is a Python package)
RUN pip install /app_andes_api/andes

# Expose the port Flask will run on
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=app_andes_api.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Command to run the Flask app
CMD ["flask", "run"]
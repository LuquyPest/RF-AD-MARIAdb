# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /Program
# Install the required system packages
RUN apt-get update && \
    apt-get install -y  \
    gcc \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    build-essential \
    python3-flask \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Copy the current directory contents into the container at /Program
COPY ./Program/ /Program

# Copy the entrypoint script into the container
COPY ./Program/entrypoint.sh /entrypoint.sh

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Make the entrypoint script executable
RUN chmod +x /entrypoint.sh

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Set the entrypoint to the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]



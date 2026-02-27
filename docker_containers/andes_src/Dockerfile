FROM xaviercasasbsc/docker_ipopt_combined

# Set the working directory to the home directory of the container
WORKDIR /home

# Set the PYTHONPATH environment variable
ENV PYTHONPATH=/home/colmenasrc:$PYTHONPATH

# Copy the 'src' folder from the host machine into the container's home directory
COPY colmenasrc/colmenasrc/ /home/colmenasrc/
COPY utils/ /home/utils/
COPY andes/ /home/andes/
COPY requirements.txt /home/
COPY main_colmena.py /home/

# Install Python dependencies
RUN pip install --break-system-packages -r /home/requirements.txt

CMD ["python3", "/home/main_colmena.py"]

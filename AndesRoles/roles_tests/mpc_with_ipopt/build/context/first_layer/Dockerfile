FROM python:3.9.18-slim-bookworm

# Set working directory and copy project
COPY . /home
WORKDIR /home
RUN python3 -m pip install .

RUN apt-get update && apt-get install -y \
    liblapack3 \
    libgfortran5 \
 && apt-get clean && rm -rf /var/lib/apt/lists/*


# Set the environment to use it
ENV PATH="/home/ipopt/bin:${PATH}"
ENV LD_LIBRARY_PATH="/home/ipopt/lib:"

ENTRYPOINT start


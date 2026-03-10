# Stage 1: Get the pre-compiled COIN-OR solvers
# This stage uses the 'coinor/coin-or-optimization-suite' image as a source for solvers.
FROM coinor/coin-or-optimization-suite AS solver-source

# Stage 2: Final image - based on Python 3.9.18 slim-bookworm
# This stage will be smaller and contain only essential components + copied solvers.
FROM python:3.9.18-slim-bookworm AS final

ENV DEBIAN_FRONTEND=noninteractive

# Install common system dependencies needed for solver runtime.
# These typically include Fortran runtime libraries (libgfortran5) and BLAS/LAPACK implementations.
# Make sure to install any specific dependencies that the copied solvers might need.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    libgfortran5 \
    libblas3 \
    liblapack3 && \
    rm -rf /var/lib/apt/lists/*

# Copy the Ipopt and GLPK executables from the 'solver-source' stage.
# We assume they are in /usr/bin in the coinor/coin-or-optimization-suite image.
COPY --from=solver-source /usr/bin/ipopt /usr/local/bin/

# Copy Ipopt shared libraries from correct path
COPY --from=solver-source /usr/lib/libipopt.so.3 /usr/local/lib/
COPY --from=solver-source /usr/lib/libipopt.so /usr/local/lib/
COPY --from=solver-source /usr/lib/libipoptamplinterface.so.3 /usr/local/lib/
COPY --from=solver-source /usr/lib/libipoptamplinterface.so /usr/local/lib/
# Optional: copy coin libraries if needed (wildcard if they exist)
COPY --from=solver-source /usr/lib/libcoin* /usr/local/lib/

# Also ensure LD_LIBRARY_PATH includes /usr/local/lib
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"

# Install Python dependencies:
RUN pip install --no-cache-dir pyomo 

# Set working directory for your application
WORKDIR /app

# Copy your test script into the image
COPY test_pyomo_ipopt.py .

# Run the test script to verify Pyomo and Ipopt integration.
# This step will confirm if the copied solvers are compatible with the bookworm base.
RUN python3 test_pyomo_ipopt.py

# Set the default command when the container starts
CMD ["bash"]

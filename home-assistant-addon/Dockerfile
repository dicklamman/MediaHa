ARG BUILD_FROM=ghcr.io/hassio-addons/base-python:13.1.2
FROM $BUILD_FROM

# Copy data for add-on
COPY . /app
WORKDIR /app

# Install requirements
# Since Flask is used but not listed, we'll add it and others
RUN pip3 install --no-cache-dir Flask ebooklib beautifulsoup4 opencc

# Make sure the script is executable
RUN chmod a+x /app/run.sh

CMD [ "/app/run.sh" ]
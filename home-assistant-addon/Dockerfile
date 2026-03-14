FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app
COPY . /app

# Install build dependencies, change line endings, and set permissions
RUN apt-get update && \
    apt-get install -y --no-install-recommends dos2unix gcc g++ && \
    rm -rf /var/lib/apt/lists/* && \
    dos2unix /app/run.sh && \
    chmod a+x /app/run.sh && \
    pip3 install --no-cache-dir Flask ebooklib beautifulsoup4 opencc mutagen musicbrainzngs requests dropbox waitress

CMD [ "/app/run.sh" ]

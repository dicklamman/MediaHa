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
    pip3 install --no-cache-dir Flask ebooklib beautifulsoup4 opencc mutagen musicbrainzngs requests dropbox waitress pykakasi

# Note: Calibre tools (calibredb) can be installed separately if needed.
# The sync will work with direct database access even without calibredb.
# To install Calibre, uncomment the following:
# RUN wget -q https://github.com/kovidgoyal/calibre/releases/download/v7.0.0/calibre-installer-linux-x64.tar.xz && \
#     tar xf calibre-installer-linux-x64.tar.xz && \
#     python3 setup.py install && \
#     rm -rf calibre-installer-linux-x64.tar.xz calibre-src

CMD [ "/app/run.sh" ]

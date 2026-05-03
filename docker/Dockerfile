FROM node:25-trixie as client
COPY client/ /opt/mediastudyshelf/client/
RUN set -o errexit -o nounset; \
  cd /opt/mediastudyshelf/client; \
  npm install; \
  npm run build

FROM python:3.14.4-trixie as server
ENV DEBIAN_FRONTEND noninteractive
RUN set -o errexit -o nounset; \
  apt-get update; \
  apt-get install -y \
    ca-certificates \
    ffmpeg;
COPY ./ /opt/mediastudyshelf/
COPY --from=client /opt/mediastudyshelf/client/dist/    /opt/mediastudyshelf/public/
RUN set -o errexit -o nounset; \
    cd /opt/mediastudyshelf; \
    pip install -e .;

WORKDIR /opt/mediastudyshelf

CMD [ "mediastudyshelf-server" ]
# QLC+ 5.2.2 built headless, for tools/qlc_check.py (see docs/qlc-live-check.md)
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive QLC_TAG=QLC+_5.2.2
RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates cmake g++ make python3 python3-pip python3-websocket \
      qt6-base-dev qt6-declarative-dev qt6-3d-dev qt6-multimedia-dev qt6-websockets-dev \
      qt6-serialport-dev qt6-svg-dev qt6-5compat-dev qt6-tools-dev 'qml6-module-*' \
      libxkbcommon-dev libusb-1.0-0-dev libasound2-dev libfftw3-dev libsndfile1-dev libudev-dev \
      qlcplus \
 && rm -rf /var/lib/apt/lists/*
# fixture definitions come from the distro package (/usr/share/qlcplus); the engine from source
RUN git clone --depth 1 --branch "$QLC_TAG" https://github.com/mcallegari/qlcplus /src \
 && cd /src && sed -i 's/^add_subdirectory(plugins)/#&/' CMakeLists.txt \
 && mkdir b && cd b && cmake .. -Dqmlui=ON && make -j"$(nproc)" qlcplus-qml
# the RGB scripts of the SAME tag (4 and 5 differ)
RUN mkdir -p /root/.qlcplus/rgbscripts && cp /src/resources/rgbscripts/*.js /root/.qlcplus/rgbscripts/
ENV LD_LIBRARY_PATH=/src/b/engine/src:/src/b/webaccess/src:/src/b/engine/audio/src \
    QLCPLUS_BIN=/src/b/qmlui/qlcplus-qml QT_QPA_PLATFORM=offscreen
WORKDIR /work

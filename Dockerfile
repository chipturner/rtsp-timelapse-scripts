FROM python:3

WORKDIR /sandbox
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN apt update
RUN apt-get install -y ffmpeg

RUN apt-get clean autoclean
RUN apt-get autoremove --yes
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/
RUN rm -rf /var/lib/apt/lists/*

ENV TZ=America/Los_Angeles
COPY . .

ENTRYPOINT [ "python", "grab-timelapse-frame.py" ]

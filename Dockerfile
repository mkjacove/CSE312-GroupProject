FROM python:3.12

ENV HOME /root
WORKDIR /root

COPY ./requirements.txt ./requirements.txt
COPY ./server.py ./server.py
COPY ./utils ./utils
COPY ./images ./images
COPY ./static ./static
COPY ./templates ./templates
COPY ./run.py ./run.py

RUN pip3 install -r requirements.txt

EXPOSE 8080

#ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.2.1/wait /wait
#RUN chmod +x /wait

COPY --from=ghcr.io/ufoscout/docker-compose-wait:latest /wait /wait

CMD /wait && python3 -u run.py
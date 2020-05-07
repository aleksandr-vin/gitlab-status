FROM python:3

WORKDIR /src

COPY requirements.txt /src/
COPY setup.py /src/

RUN pip install -r requirements.txt

COPY . /src

RUN pip install -e .

ENTRYPOINT ["ingest"]
CMD ["--no-pipelines", "--no-merge-requests", "--check-missing-intervals", "30d"]

FROM python:3.10

WORKDIR /

COPY requirements.txt /
COPY start.sh /start.sh
RUN chmod +x /start.sh
RUN pip install --upgrade pip
RUN pip install spacy
RUN python -m spacy download en_core_web_sm
RUN pip install -r requirements.txt

COPY . /

# CMD python main.py ; python test.py
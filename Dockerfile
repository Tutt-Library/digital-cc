# Dockerfile for DigitalCC
FROM tuttlibrary/python-base
MAINTAINER Jeremy Nelson <jermnelson@gmail.com>

# Set environmental variables
#ENV DIGCC_GIT https://github.com/Tutt-Library/digital-cc.git
ENV DIGCC_HOME /opt/digital-cc

# Clone master branch of Tutt Library Digitial CC repository,
# setup Python env, run 
#RUN git clone $DIGCC_GIT $DIGCC_HOME && \
#  cd $DIGCC_HOME && \
#  mkdir instance && \
#  pip install -r requirements.txt

COPY *.py $DIGCC_HOME/
COPY aristotle/ $DIGCC_HOME/aristotle/
COPY search/ $DIGCC_HOME/search/
COPY static/ $DIGCC_HOME/static/
COPY templates/ $DIGCC_HOME/templates/
COPY VERSION $DIGCC_HOME/VERSION
COPY instance/conf.py $DIGCC_HOME/instance/conf.py
#COPY supervisord.conf /etc/supervisor/conf.d/
EXPOSE 5000

WORKDIR $DIGCC_HOME
#CMD ["nohup", "gunicorn", "-b", "0.0.0.0:5000", "run:app"]
CMD ["nohup", "gunicorn", "-b", "0.0.0.0:5000", "run:app"]

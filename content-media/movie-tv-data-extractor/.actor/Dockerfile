FROM apify/actor-python:3.12

COPY requirements.txt ./
RUN echo "Python version:" \
 && python --version \
 && echo "Installing dependencies:" \
 && pip install --no-cache-dir -r requirements.txt \
 && echo "All installed Python packages:" \
 && pip freeze

COPY . ./

# Compile all source so a syntax error fails the build, not the run.
RUN python -m compileall -q src

CMD ["python", "-m", "src"]

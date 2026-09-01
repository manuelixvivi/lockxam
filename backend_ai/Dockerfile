FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements_sandbox.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app

EXPOSE 5000

ENV PORT=5000
ENV FLASK_APP=sandbox_app.py

CMD ["python", "sandbox_app.py"]

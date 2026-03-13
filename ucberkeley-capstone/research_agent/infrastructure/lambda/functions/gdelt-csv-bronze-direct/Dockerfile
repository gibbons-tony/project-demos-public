# Use AWS Lambda Python 3.11 base image
FROM public.ecr.aws/lambda/python:3.11

# Install build dependencies
RUN yum install -y gcc gcc-c++ cmake

# Copy requirements
COPY requirements.txt .

# Install Python dependencies in /asset directory
RUN pip install --no-cache-dir -r requirements.txt -t /asset

# Copy Lambda function code
COPY lambda_function.py /asset/

# The output will be in /asset
CMD ["echo", "Dependencies built successfully"]

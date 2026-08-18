# Sunday Album Pipeline Lambda Container Image
#
# One image, all 11 step handlers. Each Lambda function overrides CMD.
# Build: docker build --platform linux/amd64 -t sa-pipeline:latest .
# Push:  see scripts/build-push-lambda.sh

FROM public.ecr.aws/lambda/python:3.12

# pillow-heif ships bundled libheif wheels for Linux x86_64 — no system deps needed.
# opencv-python-headless ships bundled OpenCV binaries — no libGL needed.
# Install Python dependencies first (cached layer, only re-runs if requirements change)
COPY packages/pipeline/requirements-lambda.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt

# Copy pipeline source + handlers
COPY packages/pipeline/src/ ${LAMBDA_TASK_ROOT}/src/
COPY services/handlers/     ${LAMBDA_TASK_ROOT}/handlers/

# Verify core imports work at build time
RUN python3 -c "import cv2, numpy, PIL, pillow_heif; print('Core imports OK —', cv2.__version__, numpy.__version__, pillow_heif.__version__)"

# Default handler — overridden per Lambda function via CMD
CMD ["handlers.load.handler"]

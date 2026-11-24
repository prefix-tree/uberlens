# The environment of an AgenticVBench post-production task (python:3.12-slim, FFmpeg, the verifier's packages), with a
# coding agent added. The `uberseek` stage adds UberSeek and its skill; the `native` stage does not.
#
# Built on the host network, with the proxy and certificate bundle of the machine that builds it, because
# containers here reach the internet only through that proxy.
FROM python:3.12-slim AS native

ARG PROXY=""
COPY ca.crt /etc/build-ca.crt
ENV SSL_CERT_FILE=/etc/build-ca.crt REQUESTS_CA_BUNDLE=/etc/build-ca.crt CURL_CA_BUNDLE=/etc/build-ca.crt \
    NODE_EXTRA_CA_CERTS=/etc/build-ca.crt PIP_CERT=/etc/build-ca.crt \
    HTTPS_PROXY=${PROXY} https_proxy=${PROXY} PIP_DISABLE_PIP_VERSION_CHECK=1

RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
 && printf 'Acquire::https::CAInfo "/etc/build-ca.crt";\nAcquire::https::Proxy "%s";\n' "${PROXY}" > /etc/apt/apt.conf.d/99build \
 && apt-get update && apt-get install -y --no-install-recommends ffmpeg unzip curl ca-certificates nodejs npm git \
 && rm -rf /var/lib/apt/lists/*

# What the benchmark's own image installs for the verifier.
RUN pip install --no-cache-dir "numpy<3" "scikit-image>=0.22,<1.0" "scipy>=1.10"

RUN npm install -g opencode-ai@1.19.6 && opencode --version

# What the Sequencing and Assembly images install for their verifier.
RUN pip install --no-cache-dir "opencv-python-headless==4.13.*" && python -c "import cv2"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work /logs

FROM native AS uberseek

ENV UBERSEEK_TRANSCRIPT_MODEL=base HF_HUB_DISABLE_XET=1
COPY src /opt/uberseek
RUN pip install --no-cache-dir "/opt/uberseek[transcript]" \
 && python -c "import faster_whisper; faster_whisper.WhisperModel('base', device='cpu', compute_type='int8')"
# The skill, where OpenCode reads global rules: its core, and where to get the rest.
RUN mkdir -p /root/.config/opencode \
 && uberseek guide > /root/.config/opencode/AGENTS.md \
 && uberseek skill install /opt/skills

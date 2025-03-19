ARG BASE_IMAGE=hanzoai/desktop:latest
FROM ${BASE_IMAGE}

# Only reinstall if requirements.txt changes
COPY --chown=$USERNAME:$USERNAME operative/requirements.txt $HOME/operative/requirements.txt
RUN python -m pip install -r "$HOME/operative/requirements.txt"

# Copy desktop environment/app files
COPY --chown=$USERNAME:$USERNAME image/ $HOME
COPY --chown=$USERNAME:$USERNAME operative/ $HOME/operative/

ARG DISPLAY_NUM=1
ARG HEIGHT=800
ARG WIDTH=1280
ENV DISPLAY_NUM=$DISPLAY_NUM
ENV HEIGHT=$HEIGHT
ENV WIDTH=$WIDTH

# Default endpoints (can be overridden at runtime)
ENV APP_ENDPOINT=operative-app.hanzo.ai
ENV VNC_ENDPOINT=operative-vnc.hanzo.ai
ENV API_ENDPOINT=api.hanzo.ai

ENTRYPOINT [ "./entrypoint.sh" ]

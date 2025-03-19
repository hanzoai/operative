FROM hanzoai/os:latest

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

ENTRYPOINT [ "./entrypoint.sh" ]

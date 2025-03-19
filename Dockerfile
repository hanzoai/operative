FROM docker.io/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_PRIORITY=high

# Install base packages
RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install \
    # UI Requirements
    xvfb \
    xterm \
    xdotool \
    scrot \
    imagemagick \
    sudo \
    mutter \
    x11vnc \
    # Python/pyenv reqs
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    git \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    # Network tools
    net-tools \
    netcat \
    # PPA req
    software-properties-common && \
    # Userland apps
    sudo add-apt-repository ppa:mozillateam/ppa && \
    sudo apt-get install -y --no-install-recommends \
    libreoffice \
    firefox-esr \
    x11-apps \
    xpdf \
    gedit \
    xpaint \
    tint2 \
    galculator \
    pcmanfm \
    unzip && \
    apt-get clean

# Install noVNC
RUN git clone --branch v1.5.0 https://github.com/novnc/noVNC.git /opt/noVNC && \
    git clone --branch v0.12.0 https://github.com/novnc/websockify /opt/noVNC/utils/websockify && \
    ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html

# Setup user
ENV USERNAME=operative
ENV HOME=/home/$USERNAME

# Use a different group to avoid conflict with existing 'operative' group
RUN useradd -m -s /bin/bash -d "$HOME" -g users "$USERNAME"
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER operative
WORKDIR $HOME

# Setup pyenv
RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv && \
    cd ~/.pyenv && src/configure && make -C src && cd .. && \
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc && \
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc

ENV PYENV_ROOT="$HOME/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"
ENV PYENV_VERSION_MAJOR=3
ENV PYENV_VERSION_MINOR=11
ENV PYENV_VERSION_PATCH=6
ENV PYENV_VERSION=$PYENV_VERSION_MAJOR.$PYENV_VERSION_MINOR.$PYENV_VERSION_PATCH

RUN eval "$(pyenv init -)" && \
    pyenv install "$PYENV_VERSION" && \
    pyenv global "$PYENV_VERSION" && \
    pyenv rehash

ENV PATH="$HOME/.pyenv/shims:$HOME/.pyenv/bin:$PATH"

RUN python -m pip install --upgrade pip==23.1.2 setuptools==58.0.4 wheel==0.40.0 && \
    python -m pip config set global.disable-pip-version-check true

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

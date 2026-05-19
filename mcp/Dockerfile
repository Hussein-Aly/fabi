# sources: https://fastapi.tiangolo.com/deployment/docker/#create-the-fastapi-code
# here they use this structure:
# .
  # ├── app
  # │   ├── __init__.py (note: only need when it is a separate package)
  # │   └── main.py
  # ├── Dockerfile
  # └── requirements.txt

# step -1:  Use AlmaLinux as base image
FROM almalinux:9

# step 0: set args

ARG INSTALL_PYTEST=false
ARG JWT_ENABLED=true

#ENV JWT_ENABLED=${JWT_ENABLED}

# step 1: Set working directory
WORKDIR /code

#ARG INSTALL_PYTEST=false

# step 2: set ENV vars (e.g artifactory)
ENV PIP_TRUSTED_HOST="fabaartifactory.fabagl.fabasoft.com"
ENV PIP_INDEX_URL="https://dependency.user:Faba8888@fabaartifactory.fabagl.fabasoft.com/artifactory/api/pypi/pip/simple"
ENV JWT_ENABLED=${JWT_ENABLED}
ENV TZ=UTC

# step 3: install python3.12

# note: this worked for the plugin (needs almalinux.repo add in pre.sh):
RUN --mount=type=bind,source=almalinux.repo,target=/etc/yum.repos.d/almalinux-artifactory.repo \
    yum "--disablerepo=*" "--enablerepo=artifactory-*" install -y python3.12 python3.12-devel python3.12-setuptools python3.12-wheel python3.12-pip \
    && yum -y "--disablerepo=*" "--enablerepo=artifactory-*" upgrade \
    && yum "--disablerepo=*" "--enablerepo=artifactory-*" clean all \
    && rm -rf /var/cache/yum/*


# step 4: install/create venv (not really need since docker is already isolated)
#RUN python3.12 -m pip install --upgrade pip \
#    && python3.12 -m pip install virtualenv

# step 5: install pip dependencies
COPY ./pyproject.toml /code/pyproject.toml
COPY ./mcp_server.py /code/mcp_server.py

RUN python3.12 -m pip install .


# step 7: Expose the port FastAPI will run on
# this line is more for documentation (no functionality really)
EXPOSE 8001

# note: not sure if needed
ENV PYTHONPATH=/code/app

# just to see what file are there:
#RUN ls -al app/mbai/aiserver/

# note: run webserver with uvicorn
# maybe set time out
CMD ["python3.12", "mcp_server.py"]

# Setup
- create .env file in src/mbai/aiserver/
- check out the env.example file (in the current version it is not allowed to have other envs vars than defined in the config.py)

# Running locally (we use WSL)
- install the module by calling (this should install all the libs in pyproject.toml)
- ```cd [root dir of repo] && pip install -e .[test]```

## start the server
- start the api_server.py
- checkout 127.0.0.1:9000/docs


# Building docker locally (we rarely do that):
1. Follow instructions to install WSL Almalinux + docker (/etc/yum.repos.d/fabaartifactory-almalinux.repo: and the daemon.json are important, login with normal username worked)
    - https://enggit.fabafsc.fabagl.fabasoft.com/fsc/wiki/-/wikis/engvm/linux-on-windows-engvm#wrench-install-almalinuxos-in-wsl2
2. Get almaliux.repo from: https://fabaartifactory.fabagl.fabasoft.com/artifactory/fabasoft-master/com/fabasoft/dp/container-build-tools/[RELEASE]/container-build-tools-[RELEASE].tgz!/repo/alma-9/almalinux.repo
3. Store almalinux.repo on the same level as the Dockerfile

4. ```
   sudo docker build --progress=plain -t "lol" . && sudo docker run -d -p 9000:9000 lol
   sudo docker build --progress=plain -t "lol" --build-arg JWT_ENABLED=false . && sudo docker run -d -p 9000:9000 lol
   ```

# Upload to Cloudevel

## Setup
- you only need the src/mbai/aiserver/.env and the almalinux.repo file (from above)
- you do not need to build the docker first, this instructions below uploads the code to the cloudevel -> build the image -> runs the container
- change the cloudevel name in the commands below

## Powershell
first time:
```
plink -pw Faba8888 root@fabidemoclouddevel.sq.fabasoft.com "mkdir -p /code"
```
then: ( this is new: you just need these two lines:)
```
pscp -scp -r -pw Faba8888 C:\code\projects\ai-python-service-fabi root@fabidemoclouddevel.sq.fabasoft.com:/code 
plink -pw Faba8888 root@fabidemoclouddevel.sq.fabasoft.com "bash /code/ai-python-service-fabi/docker_start_script_clouddevel.sh"
```
## on Cloudevel
first: ssh root@fabidemoclouddevel.sq.fabasoft.com
```
cd /code/ai-python-service-fabi
docker stop ai-python-service-fabi
docker rm ai-python-service-fabi
docker rmi ai-python-service-fabi
docker build --progress=plain -t "ai-python-service-fabi" --build-arg JWT_ENABLED=false --build-arg INSTALL_PYTEST=false . 
docker run -d -p 9000:9000 --name ai-python-service-fabi ai-python-service-fabi
docker logs ai-python-service-fabi --follow
```
## checks
```
'docker ps' to check if the container is running
'docker exec -it ai-python-service-fabi bash' to switch to the bash inside the docker container
'docker logs ai-python-service --follow' to check logs
```

## check if server is available
check if the url is available in your browser (try Firefox if there are issues with other browsers, or just curl)

TODO: change to your cloudevel
http://fabidemoclouddevel.sq.fabasoft.com:9000
http://fabidemoclouddevel.sq.fabasoft.com:9000/docs -> for swagger docs

## general cleanup (not tested)
```
docker builder prune -a -f
```

## cleanup everything
```
docker system prune -a --volumes
```
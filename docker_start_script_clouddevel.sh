cd /code/ai-python-service-fabi
docker stop ai-python-service-fabi
docker rm ai-python-service-fabi
docker rmi ai-python-service-fabi
docker build --progress=plain -t "ai-python-service-fabi" --build-arg JWT_ENABLED=false --build-arg INSTALL_PYTEST=true .
docker run -d -p 9000:9000 --name ai-python-service-fabi ai-python-service-fabi
docker logs ai-python-service-fabi --follow
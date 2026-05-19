cd /code/mcp
docker stop fabi-mcp
docker rm fabi-mcp
docker rmi fabi-mcp
docker build -t "fabi-mcp" .
docker run -d -p 8001:8001 --name fabi-mcp fabi-mcp
docker logs fabi-mcp --follow
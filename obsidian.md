### HTTPS
In the section about deployment you will see how to set up HTTPS for free, using Traefik and Let's Encrypt.

### auth

### middleware

### template
https://github.com/fastapi/full-stack-fastapi-template/tree/master

### fastapi limiter
https://github.com/long2ice/fastapi-limiter
last updated: 11 months ago -> unmaintainted?, supports websockets

### slowapi
https://github.com/laurents/slowapi
more active, used by many popular projects, but doesn't support websockets

### redis
> https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/docker/
> - redis/redis-stack contains both Redis Stack server and Redis Insight. This container is best for local development because you can use the embedded Redis Insight to visualize your data. \
> `docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest`
>
> - redis/redis-stack-server provides Redis Stack server only. This container is best for production deployment. \
> `docker run -d --name redis-stack-server -p 6379:6379 redis/redis-stack-server:latest`


hence, we'll use redis/redis-stack for local development.

### issue with pytest and fastapi-limiter
https://github.com/long2ice/fastapi-limiter/issues/51

### serving the frontend
if frontend is served from a live server like that in vscode, then it must be made sure that the upload folder is not served from that server. this is because the creation of new file in the upload folder will trigger a reload of the frontend, which will break the websocket connection.


### extracting only text
as the requirement says.


### ephemeral document storage
once some kind of user auth is implemented we can make the document storage persistent. But since the current requirement does not mention user auth, we'll just delete the files after the user disconnects.

### periodic cleanup up uploads folder
in case that the client uploads files, but doesn't establish the websocket connection, the uploaded documents remain saved. These can be later deleted using a periodic cleanup task, which can be easily implemented using a cron job.
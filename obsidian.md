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
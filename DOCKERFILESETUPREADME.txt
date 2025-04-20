things I did for deployment (Handled by Mingi Hong)

Generally, followed Jesse's lecture on Deployment

- created private_key.pem and put private key of team instance into it
- used chmod to change permissions to read only to owner
- used ssh -i private_key.pem ubuntu@54.234.181.245 to log into the server

What I did in the server:
Followed instructions to install nginx on ubuntu
Followed instructions to install docker on ubuntu
configured (in nginx file) server name to be internal-server-error.cse312.dev
Followed steps to install certbot & configure domain name to use https through certbot

Tested with git clone <repo name>
Didn't work

Went to re-configure nginx default file to mirror the lecture default file very similarly (basically only the name is changed)

Went to re-configure Dockerfile and docker-compose.yml file a little bit, but just reverted it back eventually

Ran docker compose up (force build version) and it succeeded!

Pushed to second branch (used for deployment) for now
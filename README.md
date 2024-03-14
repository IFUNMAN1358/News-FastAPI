# Description:
The News-FastAPI project assumes a basic example of a news site with a modified
cookie token system, the ability to edit account data and the roles of moderator
and admin.

---

# Features:
1) Cookies with access/refresh tokens.
2) User(general)/moderator/admin roles.
3) Temporary saving of user data in redis.
4) Sending emails to the user's email
5) Full-text search in ElasticSearch.
6) Kibana interface.

---

# Manual:

**1. Configure the .env file.**

**2. Create docker-compose containers:**
* docker-compose up --build

**If called error related with HTML -> need activate two next commands with VPN.
After running commands you can off VPN.**
* docker pull docker.elastic.co/elasticsearch/elasticsearch:8.11.3
* docker pull docker.elastic.co/kibana/kibana:8.11.3

**3. Upgrade alembic revision in docker-container:**
* docker-compose exec app alembic upgrade head

**4. Go to the /docs service and activate the elastic index creation
function (admin functions block) by entering the master key from the .env file.**

---

# Creating Admin:

**You can create an admin either using the registration function or by yourself
in the postgres database. In any case, you will need to change the user role to 'admin' in the postgres
database yourself.**

An admin can create new admins and moderators, but it is highly discouraged to assign real emails to newly created admins when creating them.
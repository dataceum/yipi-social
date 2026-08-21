## Choice of Stack
FastAPI is the overall better recommendation for building pure API endpoints with separate object storage. However, Django (via Django REST Framework) remains the superior choice if your application relies on complex relational data and rapid development speed.
Since your architecture strictly separates the backend API from the storage layer (S3) and uses an RDS database, the choice comes down to whether you need a lightweight, high-performance API router or a complete, batteries-included framework.
1. High-performance APIs, microservices, real-time features.
2. Native async for S3 operations (highly concurrent, lightweight).
3. Tiny Docker images, runs efficiently on minimal ECS CPU/RAM.
4. Built-in automatic interactive docs (Swagger UI / ReDoc).

## System Architecture
### Secure Media File Uploads (S3 + CloudFront)
In your FastAPI settings.py, use django-storages[boto3] to manage your profile pictures.
1. Do not expose your raw S3 bucket URL to the internet.
2. Secure your S3 bucket completely by blocking all public access.
3. Configure CloudFront to access your bucket via an Origin Access Control (OAC) policy.
4. In FASTAPI, configure AWS_S3_CUSTOM_DOMAIN to map directly to your CloudFront distribution URL. This ensures user profile images load over a fast, secure CDN while keeping your database bucket completely private.

### Network and Database Isolation
Do not expose your RDS database to the public internet. Ensure your RDS instance is launched inside Private Subnets within your AWS VPC. Your ECS Express Mode containers will connect to the database internally across the AWS network infrastructure, keeping your customer data completely locked away from external scanning or attacks.

### Secrets Management
Never push production database strings, Django secret keys, or AWS access tokens into your Git repository.
1. For standard production, use AWS Systems Manager (SSM) Parameter Store (SecureString type). It is incredibly secure and virtually free for standard API limits.
2. Map these parameters directly into your ECS Task Definition, allowing AWS to inject them safely into your Django environment variables at startup.

## Models
In SQLModel, sa_relationship_kwargs stands for SQLAlchemy Relationship Keyword Arguments.Because SQLModel is a hybrid framework built on top of SQLAlchemy, it provides a clean, simplified syntax for standard operations. However, when you need advanced database-level configurations—like defining a strict One-to-One (1:1) relationship or setting up deletion behaviors—SQLModel doesn't have a native simplified command. Instead, it gives you sa_relationship_kwargs as an "escape hatch" to pass raw configuration arguments directly down into the underlying SQLAlchemy engine.

Why is it used in User but not in Profile?In a true One-to-One relationship, the configuration needs to be applied differently to each side of the relationship depending on which table owns the data dependency.

profile: "Profile" = Relationship(
    back_populates="user", 
    sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
)

1. "uselist": False: By default, if a table has a relationship linking to another table, SQLAlchemy assumes it is a One-to-Many relationship and prepares to return a Python list of records (e.g., user.profiles would return a list of profiles). Setting uselist=False forces the framework to load and return a single object instead of a collection (e.g., user.profile returns just one profile instance).
2. "cascade": "all, delete-orphan": This dictates cleanup rules. If a User record is completely deleted from your CRM database, this argument tells SQLAlchemy to automatically cascade that deletion and delete the associated Profile record from disk. This prevents your database from accumulating orphaned data.

We do not need sa_relationship_kwargs here because the database-level constraint is already handled by the Foreign Key field:
```Python
user_id: int = Field(foreign_key="users.id", unique=True, index=True)
```
Because the user_id field has unique=True applied to it directly inside the database table layer, the database engine physically guarantees that no two profiles can ever link back to the exact same user ID.Since the database layer already handles the structural 1:1 security constraint via the unique=True foreign key on the profile table, the Relationship() call on the Profile model simply needs to point backward to its parent (back_populates="profile"). It doesn't need to pass any special commands to handle collection structures or deletion cascades.

### Tokens for security and authentication
In production, instead of forcing the database to handle heavy session checks on every single API request, we will use a hybrid strategy. We will issue stateless JWT (JSON Web Tokens) for fast, sub-millisecond API authentication, but we will store a corresponding Refresh Token in our PostgreSQL database. This allows us to maintain a minimalist architecture while retaining the ability to revoke sessions instantly if a user logs out or an API key is compromised.
There is a One-to-Many relationship, allowing a single User to be logged into multiple devices simultaneously (e.g., a mobile phone, a laptop, and your 3CX softphone integration).

### Token Parsing
#### class TokenData() in token.py
Instead of querying your Amazon RDS database on every single incoming API request, this dependency uses a highly optimized, stateless verification pattern. It uses your application's secure secret key to verify the signature of the incoming JWT access token in memory. It only hits the database once to confirm that the user account is active and has not been administrative locked, keeping your database load minimal and your API fast.
Before decoding, we need a lightweight Pydantic schema to validate that the token's decrypted internal payload matches our system structure.

#### Security Dependancy in security.py
 It intercepts the HTTP Authorization: Bearer <JWT> header automatically, parses the token payload, and exposes the fully authenticated User object directly to your routes.

We handle phone numbers in FastAPI is by using pydantic-extra-types, which uses Google’s official phonenumbers port under the hood.
It automatically validates international phone formats, throws clean HTTP errors if a user submits an impossible number, and standardizes the output.
By default, the library outputs phone numbers in a standard tel-URI layout (e.g., tel:+1-650-253-0000). If you are saving numbers to a PostgreSQL database, you almost certainly want them formatted strictly in E.164 database format (e.g., +16502530000).

## The Authentication Endpoints (auth.py)
Using SQLModel’s Asynchronous Session, we execute the user setup pipelines. When a user creates an account, we automatically spin up their corresponding Profile row within the same atomic database transaction.


## Models Migration
1. Install alembic and ansyncpg
2. Run alembic init -t async migrations
3. Edit the alembic.ini file. Leave sqlalchemy_url = empty
4. Edit the migrations/env.py file with the model settings
5. Make sure the target database is already created
6. Run alembic revision --autogenerate -m "initial_schema" to compile the Python migration instructions
7. Run alembic upgrade head to apply the tables directly into the target database

## Run App
1. Start the FastAPI container using uvicorn app.main:app --reload.


### Managing Enums
Strategy 1: The Modern Auto-Pilot Approach (Recommended)You can use the Open Source companion package alembic-postgresql-enum. This package plugs directly into Alembic's autogenerate engine, enabling it to fully understand PostgreSQL ENUMs natively.It will automatically:Detect any new python enums and safely inject a conditional CREATE TYPE IF NOT EXISTS block.Detect when you add, remove, or rename options inside an existing Enum class and write the complex raw SQL migrations automatically.1. Install the extension package:bashpip install alembic-postgresql-enum
Use code with caution.2. Register it inside your alembic/env.py configuration:Open your alembic/env.py file and simply import the package at the top:

### API Key Generation
1. POST /api/v1/api-keys  → get new token
2. Update ApiToken in 3CX → 3CX switches to the new key immediately
3. DELETE /api/v1/api-keys/{old_id} → old key stops working


### NOTES FOR DISCUSSION
1. Should users' profiles be approved before they can engage in community activities? This will include uploading a profile picture and bio recording.
2. Should users be able to self-join rooms without approval from the rooms' creators?
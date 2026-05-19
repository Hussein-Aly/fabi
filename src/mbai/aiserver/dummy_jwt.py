dummy_jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL3NvbG9ibGl2YXRpb25tYi5zcS5mYWJhc29mdC5jb20vZm9saW8iLCJzdWIiOiJzY2h1bGxlcjAwMDFAc3EuZmFiYXNvZnQuY29tIiwiYXVkIjoiYWktcHl0aG9uLXNlcnZpY2UiLCJleHAiOjE3NzczMDk3NTcsIm5iZiI6MTc3NzI5Nzc1NywiaWF0IjoxNzc3Mjk3NzU3LCJqdGkiOiJORmtoRk9ucTlxRkdveWtaS2QvbmVvNlgiLCJzY29wZSI6IkNPTy4xLjEwMDEuMS42MDg2MzMifQ.hbhgQM8NZq8X6C0RV2vn_mFKOwrVqsJJTn3MrI-4JTE"
dummy_jwt_secret = "RmFiYTg4ODghISFMb2xBbGVuYUZhYmlvTWF0ZXVzelRlc3Q="


"""
import asyncio
import base64

from fastmcp.server.auth import JWTVerifier

verifier = JWTVerifier(
    public_key=base64.b64decode(dummy_jwt_secret),
    issuer="https://fabidemoclouddevel.sq.fabasoft.com/folio",
    audience="ai-python-service",
    algorithm="HS256",
)


async def verify():
    x = await verifier.verify_token(dummy_jwt)
    print(x)


if __name__ == "__main__":
    asyncio.run(verify())
"""

import os
os.environ["GOOGLE_ACCOUNT"] = "why"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
from life_cli import gmail_api
files = gmail_api.download_attachments(
    "1965c19786d5a2cd",
    r"C:/g/ws/repos/own/life-cli-secrets/cas",
    account="why",
)
print("downloaded:", files)

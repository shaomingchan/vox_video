# Security Policy

## Credential handling

VoxFlow does not require credentials to be stored in the repository. Supply API keys through environment variables or through ignored local configuration owned by the external whiteboard project.

Never commit:

- RunningHub member or enterprise API keys
- APIMart, MiniMax, 302.AI, OpenAI, ChatCut, or GitHub tokens
- `.env` files or local TOML/INI configuration containing credentials
- signed download URLs, OAuth callback URLs, cookies, or authorization headers
- generated project manifests if they contain temporary service URLs

Before every push, run:

```powershell
python scripts/check_secrets.py
```

The scanner reports only file names, line numbers, and rule labels. It does not echo suspected credential values.

## If a key is exposed

1. Revoke or rotate the key at the provider immediately.
2. Stop running jobs that use the exposed credential.
3. Remove the secret from the working tree and Git history.
4. Verify the rewritten history with the secret scanner before pushing again.
5. Review provider usage and billing records for unexpected activity.

Deleting a file in a later commit is not sufficient because the credential remains in earlier Git objects.

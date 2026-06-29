# GitHub Upload Steps

Run these commands from inside the cleaned project folder.

```bash
cd SDP-Modeling-Software-clean
```

Initialize Git:

```bash
git init
```

Check what will be uploaded:

```bash
git status
```

Add files:

```bash
git add .
```

Commit:

```bash
git commit -m "Initial upload of SDP modeling software"
```

Create a new empty repository on GitHub. Do not initialize it with a README, because this folder already has one.

Connect your local folder to GitHub:

```bash
git remote add origin https://github.com/YOUR_USERNAME/SDP-Modeling-Software.git
```

Rename the branch and push:

```bash
git branch -M main
git push -u origin main
```

If GitHub asks for authentication, log in through the browser or use a Personal Access Token.

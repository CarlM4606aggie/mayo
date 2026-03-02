# Joe-Gemini 🦾🤖
### The Autonomous Senior AI Maintainer

Joe-Gemini is not just a chatbot—it is a **Self-Improving Senior Technical Architect** integrated directly into your GitHub ecosystem. Powered by **Google Gemini 2.5 Flash**, it autonomously performs high-value technical maintenance, learns from every commit, and ensures your codebase stays robust, secure, and well-documented.

---

## 🚀 Key Intelligence Features

### 🧠 Cross-Repo Global Memory
Unlike standard AI bots that start fresh every time, Joe-Gemini has a **persistent memory**. It maintains a global log of successes, failures, and "lessons learned" across your entire codebase. If it discovers a clever DX improvement in one repository, it carries that insight into every other repo it manages.

### 🩺 Surgical Precision (Zero-Slop Edits)
The bot uses a sophisticated **Search/Replace block system**. It never rewrites entire files. Instead, it performs surgical, line-by-line edits. This guarantees:
- **100% preservation** of your original indentations, comments, and structure.
- **Zero Hallucination** of unrelated code.
- **Perfect PRs** that look like they were written by an expert human.

### 🏗️ Architect-Level Reasoning
Before every PR, the bot undergoes a rigorous **6-step analysis**:
1. **Developer Experience Audit**: Fixes missing setup/build/run guides.
2. **Security Scan**: Identifies vulnerabilities and insecure patterns.
3. **Logic Verification**: Finds edge cases and error-handling gaps.
4. **Consistency Check**: Ensures new code matches repo-wide patterns.
5. **Impact Ranking**: Only opens a PR if the improvement is truly meaningful.
6. **Creative Free Will**: Proactively implements "expert touches" (the cool little stuff).

---

## 🛠️ Performance Engine

- **Model**: Google Gemini 2.5 Flash (March 2026 Edition)
- **Schedule**: Autonomous Hourly Maintenance via GitHub Actions Cron.
- **Visibility**: Automatically assigns the owner, mentions @HOLYKEYZ, and requests reviews for every action.
- **Strategy**: Multimodal analysis including Repo Structure, README Context, and target source code.

---

## ⚙️ Setup & Deployment

Joe-Gemini is designed for effortless deployment as a **GitHub App** on **Vercel**.

### 1. GitHub App Configuration
- **Webhook URL**: `https://your-vercel-app.vercel.app/webhook`
- **Permissions**: Needs `Contents: Write`, `Metadata: Read`, `Pull Requests: Write`, `Actions: Write`.

### 2. Deployment
- **Environment Variables**:
    - `GEMINI_API_KEY`: Your dedicated Google AI Studio key.
    - `GITHUB_TOKEN`: For Actions-based hourly triggers.
    - `APP_ID` / `PRIVATE_KEY`: Standard GitHub App auth.
    - `CRON_SECRET`: Ensures only your Action triggers the hourly bot.

### 3. Hourly Trigger
The bot is powered by `.github/workflows/cron.yml`, calling your `/cron` endpoint every hour on the hour.

---

## ℹ️ Author
Created by **Joseph (@HOLYKEYZ)**. This bot is the culmination of advanced agentic engineering, designed to automate the technical drudgery of maintenance while providing the creative insights of a senior lead.

Happy coding! 🚀 (v2.0 - The Intelligence Update)

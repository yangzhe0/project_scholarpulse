# Literature Brief V2.0 中文指南

> 面向科研人员与课题组的零配置、多来源、可追溯文献情报与 PDF 直达 Skill。
> 对 Windows 环境做了专项适配，也可在其他具备 Python 3 的 Agent 环境中使用。

`Literature Brief` 接收自然语言研究主题，自动完成中文术语解析、英文检索式扩展、学术来源路由、日期过滤、跨来源去重、相关性筛选、**PDF 直接下载链接提取**和结构化中文研判简报生成。

当前版本：`2.0.0`
许可：MIT

## 两句话认识它

- **一句话介绍**：Literature Brief 是一个无需 API Key 的多源学术检索助手，可查找最新论文、提取开放 PDF，并生成有证据链的中文研究简报。
- **一句话用法**：调用 `$literature-brief` 并告诉它研究主题、篇数及可选日期范围，例如“检索 2 篇关于天然卫星轨道演化的最新论文”。

## 核心特色与新增特性

| 特性 | 说明 |
| :--- | :--- |
| **Windows 强化** | 适配 Windows PowerShell / CMD 控制台中文编码，并兼容常见本地代理与证书环境。 |
| **复合主题消歧** | 将“天然卫星轨道演化”“木卫二轨道共振”等多概念课题组合为收敛的英文检索式，避免只命中其中一个宽泛词。 |
| **并行来源调用** | 不同学术来源并发检索，单个来源失败不会阻塞其他来源，并在结果中完整报告状态。 |
| **交互式自解释指南** | 无需翻阅文档，直接在对话中问它：“*这个 skills 能做什么啊？*” 或 “*怎么用？*”，Agent 会主动输出能力概述、3 种常用指令模板与产出效果预览。 |
| **直达免费 PDF 全文** | 自动提取与解析各源的开放获取 PDF 直接下载链接（arXiv PDF、PMC 全文 PDF、bioRxiv PDF、Crossref 开放出版直链）。 |
| **多源覆盖（不局限于 arXiv）** | 覆盖全球期刊正式出版索引 **Crossref**（IEEE、ACM、Springer、Nature、Elsevier 等）、生物医学国家级平台 **Europe PMC**，以及 arXiv、bioRxiv、medRxiv。 |
| **绝对零配置** | 绝无商业 API Key、Token、注册账号或付费限制，开箱即用。 |
| **确定性 Markdown 骨架** | 支持 `--format markdown`，直接由底层脚本组装结构化表格与文献元数据，彻底杜绝小参数模型格式漂移。 |
| **一键健康检查** | 支持 `--health-check`，并发测试 5 大公开源的连通性与网络延迟。 |
| **历史查重排除** | 支持 `--exclude-ids`，周期性追踪时自动跳过昨天或上周已推荐的文献。 |
| **BibTeX 引用生成** | 自动生成标准 BibTeX 代码块，方便一键导入 Zotero、Mendeley 或 LaTeX。 |

---

## 开箱使用

### 1. 技能安装路径

将 `literature-brief` 文件夹放置在对应 Agent 的 Skills 目录下：

- **Codex / Claude Code**：
  ```text
  C:\Users\<你的用户名>\.codex\skills\literature-brief\
  # 或
  C:\Users\<你的用户名>\.claude\skills\literature-brief\
  ```
- **项目级集成**（如当前工作区）：
  ```text
  .\skills\literature-brief\
  ```

### 2. 对话直接调用示例

在支持该 Skill 的对话框中，直接使用自然语言交互：

- **查看技能说明**：
  > “这个 skills 能做什么啊？”
- **默认追踪最新**：
  > “帮我找一下最近关于『智能体记忆』的 2 篇最新论文”
- **指定日期范围**：
  > “检索 2026 年 8 月份关于『多模态大模型』的 3 篇文献”
- **探索性领域扫描**：
  > “做一次关于『癌症免疫治疗』的 5 篇文献速览扫描”
- **源连通性诊断**：
  > “检查一下当前学术数据源的健康状态”

---

## 命令行与底层脚本使用 (Windows PowerShell)

也可以在终端中直接运行底层脚本：

### 1. 快速健康检查
```powershell
python scripts/search_literature.py --health-check
```

### 2. 生成预排版 Markdown 简报
```powershell
python scripts/search_literature.py --topic "智能体记忆" --format markdown
```

### 3. 指定篇数与输出文件（可选）
```powershell
python scripts/search_literature.py --topic "扩散模型" --count 3 --format markdown --output brief.md
```

### 4. 排除已读历史论文
```powershell
python scripts/search_literature.py --topic "具身智能" --exclude-ids "arxiv:2608.12345,10.1234/example"
```

### 5. 查看预存学术词汇表
```powershell
python scripts/topic_expansion.py --list
```

### 6. 一键重新打包分发包
```powershell
python scripts/package_skill.py
```

打包脚本会先运行离线回归测试，再在项目根目录的 `dist` 中生成可复现 ZIP 与 SHA-256 校验文件。

---

## 来源与事实边界说明

- **关于 Google Scholar**：Google Scholar 不提供适合本技能的零凭据公开检索接口，并可能触发人机验证；本工具改用 **Crossref**、**Europe PMC** 等开放学术来源，实际可用性会受各来源服务状态与本地网络影响。
- **关于全文研判**：本工具默认进行“摘要级研判”，摘要未提供的方法与实验数据均标明“摘要未说明”，严禁凭空捏造。

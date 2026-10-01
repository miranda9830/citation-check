# citation-check · 引用核查

**[中文](#中文) | [English](#english)**

> 让文献综述里的每一条引用，都能落到原文的一句真实句子上。
> Every citation in your literature review, traced to a real sentence in the source.

---

## 中文

### 这是什么

一个 [Claude Code](https://claude.com/claude-code) Skill，专为**用英文写论文的中国留学生**设计。

它逐条核对你草稿里的引用：引用的内容是否真的出现在原文 PDF 中，原文是否真的支持你的写法。发现问题后，它会**用中文告诉你哪里有问题**，并给出**只基于原文的英文改写**，直接标注在你的 Word 原稿上。

### 为什么做这个

在英语国家读书，写 literature review 时我们常常遇到这些情况：

- 英文文献读得慢，只看了摘要就引用，不确定原文是不是这么说的
- 让 ChatGPT 帮忙写一段再补引用，结果引用是**编造的**：有作者、有页码、有引号，原文里根本没有这句话
- 自己写了一句，挂上一个"大概相关"的引用，其实原文并不支持
- 中英对照写稿，改了英文忘了改中文，或者反过来
- 老师的扣分理由是 *overclaiming* 或 *misrepresenting sources*，但自己看不出哪里写过头了

逐篇翻 PDF 核对太慢，deadline 前根本做不完。这个 skill 帮你做这件事。

### 它能查出什么

| 问题类型 | 例子 |
|---|---|
| **编造引用** | 引号里的句子在原文中根本不存在 |
| **因果夸大** | 原文说 *associated with*（相关），你写成了 *causes*（导致） |
| **人群 / 地区扩大** | 原文研究美国成年人，你写成了澳大利亚青少年 |
| **数字错误** | 原文最终样本 282 篇，你写成了 381 篇 |
| **引用覆盖不全** | 一个引用挂在句尾，只支持了句子的一半 |
| **二手引用** | 那句话其实是原文作者引用别人的观点，你却标成了原文作者的 |
| **页码错误** | 原句存在，但不在你标注的那一页 |

### 核心设计：防幻觉不靠 AI "自觉"，靠脚本

AI 最危险的地方，是它编出来的引用**看起来非常专业**。所以这个 skill 不相信 AI 自己说的"我查过了"：

**报告里出现的每一句"原文原句"，都要由脚本在 PDF 中逐字比对。比对不上的会被自动删除，对应条目降级为"未定位"。** 就算 AI 编了一句引文，它也进不了你的报告。

| 情况 | 结果 |
|---|---|
| 与 PDF 逐字一致 | ✅ 通过 |
| 只有 PDF 排版差异（断行连字符、ﬁ/ﬂ 连字、弯引号、文本层缺空格等） | ✅ 通过 |
| 换了一个实义词（比如 digital → AI） | ❌ 拦截，并指出是哪个词不同 |
| 原文中不存在 | ❌ 拦截 |

另外两条原则：
- **找不到 ≠ 你引错了**：没定位到就标 ⚪ 提醒你自己确认，不会误报成"你引错了"。
- **不上网"补"原文**：只用你提供的 PDF。缺 PDF 就标 ⚫ 告诉你，不会拿网上的摘要或 AI 的记忆顶替。

### 你会得到什么

核查完成后，在草稿所在文件夹生成两个 Word 文件。

**1. 批注版原稿 `草稿名_批注版.docx`**：你原稿的副本，原文件不会被改动。

> **【原句 Original】** …and digital transformation <mark>consistently improves firms' financial performance</mark> (Vial, 2019). **【改写句 Rewrite】** *…and digital transformation is associated with increases in several dimensions of organizational performance, including financial performance, although it can also be associated with undesirable outcomes (Vial, 2019).*
>
> **【原句 Original】** …而<mark>数字化转型会持续提升企业的财务绩效</mark>（Vial, 2019）。**【改写句 Rewrite】** *…而数字化转型与包括财务绩效在内的多项组织绩效提升相关，但也可能带来不良结果（Vial, 2019）。*

- 只高亮出问题的那几个词：🔴 红色 = 与原文不一致，🟡 黄色 = 部分支持，灰色 = 需要你自己确认
- **中英对照稿**里，中文译句也会同步标注，改稿时不会漏改
- 每处问题附带一条 Word 批注：**中文 + 英文**问题说明、原文原句和页码、中英文改写
- 改写**只使用原文里有的信息**；原文完全不支持的句子，会建议删除或另找来源，不会硬凑一句看似有依据的话

**2. 核查报告 `草稿名_引用核查报告.docx`**：一张中英双语的总表，可以直接转给导师看。

| 草稿句子 | 引用 | 论点 → 原文原句（PDF 页码） | 状态 | 问题说明 | 建议改写 |
|---|---|---|---|---|---|

状态分为 5 种：🟢 有证据支持 · 🟡 部分支持 · 🔴 与原文不一致 · ⚪ 未定位，请自己确认 · ⚫ 缺少 PDF

### 安装

1. 安装 [Claude Code](https://claude.com/claude-code)，以及 Python 3.9 或更高版本
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 把本仓库放到 Claude Code 的 skills 目录，文件夹名为 `citation-check`：
   - Windows：`C:\Users\<你的用户名>\.claude\skills\citation-check\`
   - macOS / Linux：`~/.claude/skills/citation-check/`

   也可以直接克隆：
   ```bash
   git clone https://github.com/<GitHub用户名>/citation-check.git ~/.claude/skills/citation-check
   ```

### 使用

在 Claude Code 里用中文直接说就行：

> 帮我核对 `D:\论文\2.1文献综述.docx` 的引用，PDF 在 Zotero 里

> 帮我核对这份草稿的引用，原文 PDF 在 `D:\论文\参考文献` 文件夹

> ChatGPT 说 Vial (2019, p. 12) 原文写了 "……"，帮我核一下是不是真的

支持的原文来源：
- **Zotero 文献库**：按"作者 + 年份"自动匹配，并用参考文献列表中的标题区分同一作者的不同论文
- **你指定的文件夹**
- **直接给出的 PDF 文件**

### 工作流程

```
草稿.docx
  → extract_citations.py  抽取带引用的英文句子（中英对照稿自动跳过中文句），解析参考文献列表
  → find_sources.py       在 Zotero / 指定文件夹中找到对应的 PDF
  → pdftool.py            Claude 阅读原文：关键词定位 → 摘出原句 → 逐字验证
  → Claude 判断           拆分论点，逐个检查：覆盖 / 因果强度 / 人群 / 地区 / 数字 / 二手引用
  → build_report.py       再次逐字复核全部引文 → 生成双语报告 + 批注版原稿（annotate_draft.py）
```

### 局限

- 扫描版 PDF（没有文字层）提取不到文字，这类引用会标为 ⚪ 未定位
- 页码是 PDF 文件的页序，可能与期刊印刷页码不同
- 目前识别 APA 格式的文内引用：括号式 (Author, Year) 和叙述式 Author (Year)
- "原文是否支持"的判断仍由 AI 完成。脚本保证的是**原句真实存在**；最终结论请你对照原文确认，尤其是交作业或投稿前

---

## English

### What it is

A [Claude Code](https://claude.com/claude-code) Skill built for **Chinese international students writing academic papers in English**.

It checks every citation in your draft: does the cited content actually appear in the source PDF, and does the source really support what you wrote? Problems are **explained in Chinese and English**, with **English rewrites that stay strictly within the evidence**, marked directly on your Word draft.

### Why

When writing a literature review in a second language, it is easy to:

- cite a paper after reading only the abstract, without being sure it really says that
- let ChatGPT draft a paragraph and add citations, and end up with **fabricated quotes**: real-looking authors, page numbers and quotation marks, but the sentence is not in the paper
- attach a "roughly related" citation that does not actually support the claim
- lose track of changes between the Chinese and English versions of a bilingual draft
- lose marks for *overclaiming* or *misrepresenting sources* without seeing where it happened

Checking every PDF by hand takes too long before a deadline. This skill does it for you.

### What it catches

| Issue | Example |
|---|---|
| **Fabricated quotes** | The quoted sentence does not exist in the source |
| **Causal overclaiming** | Source says *associated with*; draft says *causes* |
| **Population / geography drift** | Source studied US adults; draft says Australian adolescents |
| **Wrong numbers** | Final sample was 282 works; draft says 381 |
| **Partial coverage** | One citation at the end of a sentence supports only half of it |
| **Secondary citation** | The idea belongs to someone the source is quoting |
| **Wrong page** | The sentence exists, but not on the cited page |

### Core design: anti-hallucination by script, not by trust

**Every "source quote" in the output is matched word-for-word against the PDF by a script. Anything that does not match is removed automatically and the item is downgraded.** Even if the model invents a quote, it cannot reach your report.

| Case | Result |
|---|---|
| Identical to the PDF | ✅ pass |
| PDF layout differences only (line-break hyphens, ﬁ/ﬂ ligatures, curly quotes, missing spaces in the text layer) | ✅ pass |
| One content word changed (e.g. digital → AI) | ❌ blocked, with the differing word shown |
| Not in the PDF | ❌ blocked |

Also:
- **Not found ≠ wrong.** Unlocated passages are marked ⚪ for you to check, never reported as errors.
- **No web look-ups.** Only your PDFs are used. Missing PDFs are marked ⚫; nothing is filled in from abstracts or model memory.

### Output

Two Word files next to your draft:

1. **`<draft>_批注版.docx`**: an annotated copy of your draft (the original is untouched). Problem phrases are highlighted; each problem sentence is labelled **【原句 Original】** and followed by **【改写句 Rewrite】**. Chinese sentences in bilingual drafts are marked too. Each problem has a Word comment with the issue in Chinese and English, the verified source quote with page number, and the suggested rewrite.
2. **`<draft>_引用核查报告.docx`**: a bilingual summary table (draft sentence, citation, claims → verified source quotes, status, issue, suggested rewrite) that you can share with your supervisor.

Statuses: 🟢 Supported · 🟡 Partially supported · 🔴 Contradicted · ⚪ Not located, please check · ⚫ Source PDF missing

### Install

1. Install [Claude Code](https://claude.com/claude-code) and Python 3.9+
2. `pip install -r requirements.txt`
3. Put this repository in your Claude Code skills folder as `citation-check`:
   - Windows: `C:\Users\<you>\.claude\skills\citation-check\`
   - macOS / Linux: `~/.claude/skills/citation-check/`

### Usage

Ask Claude Code in Chinese or English, e.g.:

> Check the citations in `D:\thesis\lit-review.docx`; the PDFs are in my Zotero library.

> ChatGPT says Vial (2019, p. 12) wrote "…". Is that real?

Sources can come from your **Zotero library** (matched by author + year, disambiguated by reference-list titles), **a folder you specify**, or **PDF files you provide**.

### Limitations

- Scanned PDFs without a text layer cannot be read; those citations are marked ⚪
- Page numbers follow PDF page order and may differ from printed journal pages
- In-text citations are recognised in APA style: (Author, Year) and Author (Year)
- Whether a source *supports* a claim is still judged by the model. The script guarantees that **quoted source sentences really exist**; please confirm the final judgement against the source before submitting

---

## Author · 作者

刘馨心 (Xinxin Liu)

## License · 许可证

[MIT](LICENSE)

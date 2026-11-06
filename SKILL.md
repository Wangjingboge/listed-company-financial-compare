---
name: listed-company-financial-compare
version: "1.2.0"
display_name: A股财报分析-望京博格版
display_name_en: A-Share Financial Report Analysis (WJ Bogle Edition)
description: 输入一家或多家上市公司名称，抓取最近三个完整会计年度的财务数据，产出一份单页 HTML 财报分析报告——单公司做财报体检，多公司做横向对比；固定覆盖营收与盈利增速、收入来源结构、近三年估值水平（PE/PB 及历史分位数）和综合评价。当用户提到"分析某公司财报""看下某公司近三年营收/利润/估值""对比 A 和 B 的财务数据""这两家公司谁更好/选哪个""做个财报对比"时使用。
description_zh: 输入一家或多家 A 股上市公司名称，用 Wind 抓取最近三个完整会计年度的财务数据，产出单页 HTML 财报分析报告。固定覆盖四块内容：近三年营收与盈利增速及其匹配度、按产品口径拆分的收入来源结构迁移、近三年 PE/PB 年末序列与当前历史分位数、四维评分（成长/盈利/结构/估值）加亮点与风险的综合评价。输入一家公司时输出完整体检报告，两家及以上自动切换为横向对比版，多一列差值、一张关键指标对比表和条件化情景建议表。报告为单文件、图表全部手写 SVG、离线可开可打印。当用户问"分析某公司财报""看下某公司近三年营收利润估值""对比 A 和 B 的财务数据""这两家公司谁更好/选哪个""做个财报对比"时使用。
description_en: Builds a single-page HTML financial report for one or more A-share listed companies, pulling the last three full fiscal years of data via Wind. Every report covers four fixed blocks — revenue and net-profit growth with their alignment, revenue mix migration by product segment, three-year year-end PE/PB series with current historical percentiles, and a four-dimension scorecard (growth / profitability / mix / valuation) with highlights and risks. A single company yields a full financial check-up; two or more companies automatically switch to a side-by-side comparison with a delta column, a key-metric table, and scenario-based suggestions. Output is a self-contained file with hand-written SVG charts that opens and prints offline. Use it for "analyze this company's financials", "show me the last three years of revenue, profit and valuation", "compare A and B", or "which of these two is the better pick".
agent_created: true
---

# A股财报分析 · 望京博格版

输入公司名 → 取数 → 组装 JSON → 渲染单页 HTML。报告固定包含四块：**增速、收入结构、估值、评价**。

单公司与多公司走同一套流程，只是版式自动切换（1 家 = 体检，≥2 家 = 对比 + 差值列 + 情景建议）。

## 一、执行流程

| 步骤 | 动作 | 产出 |
|---|---|---|
| 0 | 解析用户输入，拆出公司名列表 | 1 个或多个公司名 |
| 1 | `get_stock_basicinfo` 确认代码、行业、主营 | 锁定标的，排除同名歧义 |
| 2 | 按 `references/data-playbook.md` 的四个问法取数 | 原始返回 |
| 3 | 组装 `data.json`（schema 见第三节） | 中间数据 |
| 4 | 运行 `scripts/build_report.py` | 单页 HTML |
| 5 | `present_files` 打开报告 + 三句话口头结论 | 交付 |

**输入解析规则**：

- 用户只给一个公司 → 单公司模式，报告为完整财务体检。
- 用户给两个及以上公司 → 对比模式。**所有指标必须在同一次工具调用里一起问**（分两次问会导致列名漂移、口径不一致，对比结论直接错）。
- 用户没说公司名，只说"帮我对比一下" → 问一句要对比哪几家，不要自己编。
- 用户给的是简称且可能歧义（"平安""中信""中金"）→ 先 basicinfo 查，仍不唯一就反问，别猜。
- 用户额外提了要求（"只看近三年营收""加上分红"）→ 主报告照常出，附加项放进评价段落，不额外加模块。

## 二、取数（Wind MCP）

四个工具调用即可覆盖全部需求，问法模板与返回结构解析见 `references/data-playbook.md`（**动手前必读**，内含实测返回样例、字段映射和踩坑记录）。

1. **财务三年**：`get_stock_fundamentals` —— 营收、归母净利、两者同比、ROE、销售毛利率。
2. **收入构成**：`get_stock_fundamentals` —— 问"年报主营业务收入构成，按产品分类的收入金额和占比"。
3. **估值**：`get_stock_fundamentals` —— 年末 PE(TTM)/PB 序列 + 当前值 + 近三年分位数。
4. **公司档案**：`get_stock_basicinfo` —— 行业分类、主营简介。

> 若某类数据取不到（新股、退市、港股口径缺失），把对应字段留空或写 `null`，在 `data_note` 里注明缺失原因。**绝不凭记忆补数**。

## 三、组装 data.json

```json
{
  "report_date": "2026-10-29",
  "periods": ["2023", "2024", "2025"],
  "data_note": "可选：数据待复核 / 缺失说明，会显示为报告头部的红色标签",
  "verdict": {
    "title": "一句话结论，含最关键的对比判断",
    "paragraphs": ["第1段：增速与盈利质量", "第2段：收入结构变化", "第3段：估值与性价比"],
    "scenarios": [
      {"condition": "若你更看重确定性分红", "pick": "A 公司", "why": "理由，必须带数字"}
    ]
  },
  "companies": [
    {
      "name": "贵州茅台", "code": "600519.SH", "industry": "白酒 · 食品饮料",
      "revenue": [1476.94, 1708.99, 1688.38],
      "revenue_yoy": [18.04, 15.66, -1.20],
      "net_profit": [747.34, 862.28, 823.20],
      "net_profit_yoy": [19.16, 15.38, -4.53],
      "roe": [36.18, 38.43, 34.46],
      "gross_margin": [91.96, 91.93, 91.18],
      "segments": {
        "dimension": "按产品",
        "items": [
          {"name": "茅台酒", "values": [1265.89, 1459.28, 1465.00], "shares": [85.99, 85.53, 86.80]}
        ]
      },
      "valuation": {
        "pe": [30.46, 23.15, 19.16], "pb": [11.19, 9.22, 7.60],
        "pe_now": 20.43, "pb_now": 6.62, "pe_pct": 37.79, "pb_pct": 13.10
      },
      "scorecard": {"growth": 3.5, "profitability": 5.0, "segment": 4.5, "valuation": 3.5},
      "comment": "80–120 字的经营质量判断",
      "highlights": ["3 条以内的亮点，每条带数字"],
      "risks": ["3 条以内的风险，每条带数字"]
    }
  ]
}
```

字段约定：

- 所有数组长度必须等于 `periods` 长度，顺序一一对应。**缺年份填 `null`（仅估值序列允许，其余指标不允许）**。
- 金额单位统一为**亿元**；港股/美股按记账本位币换算到"亿"，并在 `industry` 或 `data_note` 里注明币种。
- `pe_pct` / `pb_pct` 填数据源原值即可，脚本会自动识别 0–1 小数与 0–100 百分数。
- `scorecard` 四维、0–5 分，锚点见 `references/analysis-playbook.md`。
- `segments.items` 取主营构成前 3–4 项，`shares` 填原始占比（合计超 100% 属正常，脚本会归一化绘制）。

## 四、渲染

```bash
python <skill>/scripts/build_report.py data.json -o 报告.html
```

- 输出单文件 HTML，内联 CSS + SVG，离线可开、可打印。
- 版式自动适配：1 家公司不出差值列、不出现情景建议；≥2 家自动加"关键指标横向对比"与"情景选择"。
- 渲染完先 `present_files` 打开，确认没有空白模块再交付。
- 脚本报错优先检查：`periods` 与各数组长度是否对齐、`companies` 是否为空。

## 五、评价怎么写

评价是这个报告的立身之本，不要写成数据复述。

1. **先给判断，再给依据**。`verdict.title` 必须是一句有立场的话（谁更强、问题在哪），不是"两家各有优劣"。
2. **增速要拆开看**：营收增速与净利增速的背离方向，比绝对水平更有信息量。净利增速持续低于营收增速 = 盈利能力在恶化（成本、费用或价格战）；反之 = 经营杠杆在释放。
3. **收入结构看迁移方向**，不是看单年占比。高毛利主品占比连年下滑、低毛利副业占比抬升 = 结构性降级，必须在风险里点名。
4. **估值必须与增速配对解读**：
   - 低分位 + 增速稳 = 真便宜；
   - 低分位 + 增速崩 = 价值陷阱，估值还会下修；
   - **高分位 + 利润腰斩 = PE 被动抬升，不是变贵，是分母塌了**，此时看 PB 更有意义。这条最容易写错。
5. **对比结论要给条件化框架**（`scenarios`），不要说"A 更好"就结束——不同资金属性和持有期应选不同的公司。
6. 所有判断必须能在报告里的数字上找到支撑，禁止出现报告中没有的指标。

打分锚点、行业特例（银行/保险/券商无毛利率、周期股估值失效、次新股无三年数据）见 `references/analysis-playbook.md`。

## 六、红线

- 数据只来自工具返回，不推测、不估算、不补全。
- 同比变动绝对值超过 30% 的，必须换一种问法复核一次；复核不一致或明显违背行业常识时，写入 `data_note` 并在报告里标注"数据待复核"，不得直接当作事实展开论述。
- 报告末尾必须带免责声明（脚本已内置默认文案，除非用户另有要求不要删除）。
- 涉及买卖判断时只用"若……则……"的条件句式，不给目标价、不给仓位。

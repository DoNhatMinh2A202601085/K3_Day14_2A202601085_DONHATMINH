# Day 14 — Exercises

## AI Evaluation & Benchmarking · Lab Worksheet

**Thời gian làm bài:** 09:15–12:00

**Domain:** Northstar University Student Services

Điền trực tiếp câu trả lời vào file này. Golden dataset 20 QA được viết một lần
duy nhất trong `golden_dataset.json`, không chép lại toàn bộ vào Markdown.

---

Từ 09:15–09:30, cài môi trường và chạy baseline tests theo `guide_lab.md`.

---

## Part 1 — Warm-up (09:30–09:45)

### Exercise 1.1 — RAGAS Metric Thresholds

Theo bài giảng:

- 0.8–1.0: Good — monitor, maintain.
- 0.6–0.8: Needs work — analyze failures, iterate.
- Dưới 0.6: Significant issues — investigate.

Với từng metric, xác định khi nào score thấp có thể chấp nhận và khi nào là
critical.

| Metric | Acceptable Low Score Scenario | Critical Low Score Scenario | Action Required |
|---|---|---|---|
| Faithfulness | Trên factual lookup queries đơn giản, nơi context rõ ràng và answer ngắn gọn. Một số synonymous expressions có thể làm overlap thấp dù thực chất đúng. | Khi answer chứa hallucination nghiêm trọng — claim không tồn tại trong context, đặc biệt với dữ liệu quan trọng (deadlines, amounts, policies). Đây là vấn đề trust/safety. | Điều tra retrieval và prompt. Có thể cần thêm grounding guardrail hoặc cải thiện context quality. |
| Answer Relevance | Khi question ambiguous hoặc có nhiều cách diễn đạt cùng một ý; answer đúng nhưng không dùng từ khóa y hệt question. | Khi answer hoàn toàn không giải quyết intent của question — ví dụ hỏi về deadline, trả lời về eligibility. Đây là signal của prompt/routing issue. | Kiểm tra intent detection và prompt alignment. Điều chỉnh prompt để focus vào question intent. |
| Context Recall | Khi corpus có nhiều redundant information; retriever lấy đủ evidence nhưng union overlap không cao do paraphrase. | Khi retriever miss critical evidence chunks — đặc biệt với multi-document questions hoặc Hard/Adversarial cases. Recall thấp kéo theo Completeness thấp. | Cải thiện retriever (BM25 parameters, embedding model, chunk size) hoặc query expansion. |
| Context Precision | Khi có nhiều relevant chunks nhưng ranking không tối ưu; early chunks đúng nhưng system lấy thêm noise phía sau. | Khi top-ranked chunk hoàn toàn irrelevant — user chỉ đọc đầu tiên và bỏ qua phần còn lại. Precision collapse ở rank 1 là critical. | Cải thiện reranking hoặc retrieval scoring. Kiểm tra query-document alignment logic. |
| Completeness | Khi expected answer có nhiều optional details mà actual answer bỏ qua; thiếu edge cases hoặc exceptions không ảnh hưởng core correctness. | Khi thiếu mandatory information — conditions, deadlines, required steps — khiến answer không actionable. Đặc biệt critical với procedural questions. | Tăng retrieval coverage và điều chỉnh generation prompt để include all conditions/exceptions. |

### Exercise 1.2 — Bias trong LLM-as-a-Judge

Ba bias thường gặp:

- Position bias: judge ưu tiên answer xuất hiện trước.
- Verbosity bias: judge ưu tiên answer dài hơn.
- Self-preference: judge ưu tiên output giống chính model đó.

**Câu 1: Thiết kế experiment phát hiện position bias với ít nhất hai conditions.**

> **Experiment thiết kế:**
>
> Chuẩn bị N cặp (answer_A, answer_B) có chất lượng tương đương (đã được human label đồng ý là cùng điểm). Điều kiện:
>
> - **Condition 1 (A trước):** Gửi judge prompt với answer_A xếp TRƯỚC answer_B. Đo distribution scores cho A vs B.
> - **Condition 2 (B trước):** Gửi cùng cặp nhưng answer_B xếp TRƯỚC answer_A. Đo distribution scores cho B vs A.
>
> Nếu trong Condition 1 answer_A được score cao hơn đáng kể so với Condition 2, và ngược lại cho B, thì position bias tồn tại. Measure bằng paired t-test hoặc Wilcoxon giữa hai conditions trên cùng cặp answers. Cần ít nhất 30–50 pairs để có statistical power đủ.

**Câu 2: Làm thế nào giảm verbosity bias bằng rubric design?**

> Ba cách dùng rubric design giảm verbosity bias:
>
> 1. **Normalize by answer length:** Yêu cầu judge đánh giá content density (information per token), không phải raw length. Rubric nêu rõ: "Score 5 không phải vì dài, mà vì mỗi sentence đều bổ sung evidence hoặc clarification mới."
> 2. **Anti-redundancy clause:** Thêm dimension "Conciseness" vào rubric. Trừ điểm nếu answer lặp lại cùng một ý nhiều lần bằng cách khác nhau. Structure rubric: `(Content_Score × 0.7) + (Conciseness_Score × 0.3)`.
> 3. **Length cap trong prompt:** Judge prompt chỉ rõ "Evaluate the first 200 tokens of each answer equally, ignoring extra content beyond that cap." Việc cắt ngang giúp answer ngắn không bị disadvantaged về sheer volume.

**Câu 3: Tại sao cần calibrate LLM judge với human labels?**

> Ba lý do chính:
>
> 1. **Absolute vs relative scoring:** LLM judge score trên thang 1–5 nhưng không có intrinsic meaning — "4" có thể là "good" hoặc "average" tùy model. Human labels gắn score với ground truth thực, tạo anchor point để interpret judge scores đúng.
> 2. **Calibration drift:** LLM có thể trở nên stricter hoặc lenient hơn theo thời gian, temperature, hoặc minor prompt changes. Retraining hoặc prompt update cần re-calibrate để đảm bảo scores nhất quán.
> 3. **Domain-specific nuance:** Generic "correct" vs "incorrect" khác với nuanced domain như Student Services. Human labels từ domain expert điều chỉnh judge hiểu đúng context — ví dụ, missing deadline date là critical hơn missing a secondary contact method.

### Exercise 1.3 — Evaluation trong CI/CD

**Câu 1: Chọn threshold để block deployment.**

| Metric | Threshold | Lý do |
|---|---:|---|
| Faithfulness | **0.75** | Faithfulness dưới 0.75 nghĩa là >25% claims trong answer không có evidence. Với Student Services, hallucination về policy/deadline có thể gây hậu quả nghiêm trọng cho sinh viên. Đây là safety-critical metric không thể compromise. |
| Answer Relevance | **0.70** | Relevance thấp nghĩa là answer không giải quyết question intent. Trong Student Services, một irrelevant answer lãng phí thời gian người dùng và có thể dẫn đến action sai. Threshold 0.70 cho phép minor paraphrase differences nhưng vẫn reject off-topic responses. |
| Completeness | **0.70** | Completeness dưới 0.70 nghĩa là answer bỏ sót >30% required information (conditions, steps, exceptions). Với procedural questions (registration, refund process), incomplete answer gây bad user experience và có thể require repeated interactions. |

**Câu 2: Khi nào dùng offline evaluation, online evaluation và human review?**

> - **Offline evaluation:** Dùng khi cần đánh giá trước khi release (CI/CD gate) hoặc sau prompt/retriever/threshold change. Chạy tự động trên golden dataset cố định — nhanh, repeatable, không cần user real traffic. Phù hợp cho regression testing và A/B comparison giữa các model/prompt versions. Trong lab này, `pytest` và `evaluate_answers.py` là offline evaluation.
>
> - **Online evaluation:** Dùng khi cần monitor hệ thống đang chạy production với real user traffic. Thu thập actual user feedback, task completion rate, học từ distribution thật mà golden dataset không cover được. Phù hợp khi có đủ volume để detect shifts — ví dụ Langfuse, LangSmith tracking real-time metrics.
>
> - **Human review:** Dùng khi cần đánh giá high-stakes cases (scholarship appeals, policy exceptions), khi automated metrics không đủ nuanced, hoặc để calibrate LLM judge. Đắt và chậm nên reserved cho edge cases mà automated pipeline không xử lý được hoặc khi baseline metric thay đổi đáng kể cần human verification trước khi deploy.

---

## Part 2 — Core Coding (09:45–10:40)

Hoàn thiện các TODO bắt buộc trong `template.py`.

### Task 1 — Data Models

- `QAPair`: question, expected answer, gold context, metadata và retrieved contexts.
- `EvalResult`: answer-side scores, optional retrieval scores, pass/failure fields.
- `overall_score()`: trung bình Faithfulness, Relevance và Completeness.

### Task 2 — RAGASEvaluator

Answer-side:

- `evaluate_faithfulness(answer, context)`
- `evaluate_relevance(answer, question)`
- `evaluate_completeness(answer, expected)`

Retrieval-side:

- `evaluate_context_recall(contexts, expected)`
- `evaluate_context_precision(contexts, expected)`

Full pipeline:

- `run_full_eval(..., contexts=None)` luôn tính ba answer metrics.
- Nếu có `contexts`, tính và lưu thêm Context Recall và Context Precision.
- Retrieval scores không làm thay đổi `overall_score()` và pass rule gốc.

### Task 3 — LLMJudge

- `score_response(question, answer, rubric)`
- `detect_bias(scores_batch)`

### Task 4 — BenchmarkRunner

- `run(qa_pairs, agent_fn, evaluator)`
- `generate_report(results)`
- `run_regression(new_results, baseline_results)`
- `identify_failures(results, threshold)`

`BenchmarkRunner.run()` phải truyền `pair.retrieved_contexts` vào
`run_full_eval()`. Report phải có average của hai retrieval metrics.

### Task 5 — FailureAnalyzer

- `categorize_failures(failures)`
- `find_root_cause(failure)`
- `generate_improvement_suggestions(failures)`
- `generate_improvement_log(failures, suggestions)`

Kiểm tra:

```bash
pytest tests/ -v
```

`rerank_by_overlap()` là TODO bonus của Exercise 3.5. Test tương ứng được skip
nếu bạn chưa làm bonus.

---

## Part 3 — Golden Dataset & Real Benchmark (10:40–11:35)

### Exercise 3.1 — Build the Golden Dataset

Thiết kế và validate dataset theo Mục 5–6 trong `guide_lab.md`. Nội dung 20 QA
được điền trực tiếp trong `golden_dataset.json`; phần dưới chỉ ghi lại kết quả
và quyết định thiết kế, không chép lại toàn bộ QA.

**Kết quả dataset**

| Hạng mục | Kết quả |
|---|---|
| Tổng số records | ____ / 20 |
| Easy | ____ / 5 |
| Medium | ____ / 7 |
| Hard | ____ / 5 |
| Adversarial | ____ / 3 |
| Source documents được sử dụng | ____ / 10 |
| Validator status | PASS / FAIL |

**Ba case đại diện cho quyết định thiết kế**

| ID | Difficulty | Source document(s) | Vì sao case phù hợp với difficulty/attack type? |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

**Điểm khó nhất khi xây dựng expected answer hoặc evidence là gì?**

> *Câu trả lời:*

**Xác nhận:**

- [ ] Mọi claim trong expected answer đều có evidence hỗ trợ.
- [ ] Không có questions trùng ý và không dùng kiến thức ngoài corpus.
- [ ] `python validate_golden_dataset.py` báo `PASS`.

### Exercise 3.2 — Benchmark Run

Chạy:

```bash
python domain_assistant.py
python evaluate_answers.py
```

Copy bảng terminal vào đây hoặc điền từ `artifacts/benchmark_results.json`.

| ID | Question (short) | Ctx Recall | Ctx Precision | Faithfulness | Relevance | Completeness | Overall | Passed? | Failure Type |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| E01 | | | | | | | | | |
| E02 | | | | | | | | | |
| E03 | | | | | | | | | |
| E04 | | | | | | | | | |
| E05 | | | | | | | | | |
| M01 | | | | | | | | | |
| M02 | | | | | | | | | |
| M03 | | | | | | | | | |
| M04 | | | | | | | | | |
| M05 | | | | | | | | | |
| M06 | | | | | | | | | |
| M07 | | | | | | | | | |
| H01 | | | | | | | | | |
| H02 | | | | | | | | | |
| H03 | | | | | | | | | |
| H04 | | | | | | | | | |
| H05 | | | | | | | | | |
| A01 | | | | | | | | | |
| A02 | | | | | | | | | |
| A03 | | | | | | | | | |

**Aggregate Report**

- Overall pass rate: ____%
- Avg Context Recall: ____
- Avg Context Precision: ____
- Avg Faithfulness: ____
- Avg Relevance: ____
- Avg Completeness: ____
- Failure type distribution: ____

**Ba cases có Overall Score thấp nhất**

1. ID: ____ | Score: ____ | Failure type: ____
2. ID: ____ | Score: ____ | Failure type: ____
3. ID: ____ | Score: ____ | Failure type: ____

**Nhận xét ngắn:** Metric nào yếu nhất? Kết quả gợi ý vấn đề nằm ở retrieval
hay generation?

> *Câu trả lời:*

### Exercise 3.3 — LLM-as-a-Judge Rubric Design

Thiết kế rubric domain-specific cho Student Services. Mỗi mức phải đủ cụ thể để
hai người chấm độc lập có thể hiểu giống nhau.

Chọn 3–5 dimensions:

- [ ] Correctness
- [ ] Completeness
- [ ] Relevance
- [ ] Evidence/citation
- [ ] Actionability
- [ ] Safety/privacy
- [ ] Tone/clarity
- [ ] Dimension khác: __________

| Score | Tiêu chí domain-specific | Ví dụ response |
|---:|---|---|
| 5 | | |
| 4 | | |
| 3 | | |
| 2 | | |
| 1 | | |

**Ba edge cases khó chấm**

| Edge Case | Tại sao khó chấm? | Rubric xử lý thế nào? |
|---|---|---|
| | | |
| | | |
| | | |

**Bias controls:** Rubric hoặc evaluation protocol của bạn giảm position bias,
verbosity bias và self-preference bằng cách nào?

> *Câu trả lời:*

### Exercise 3.4 — Framework Comparison (Bonus +10)

Chỉ làm sau khi hoàn thành 3.1–3.3. Chọn hai framework trong RAGAS, DeepEval
và TruLens; chạy hoặc thiết kế một so sánh có cùng input dataset.

| Tiêu chí | Framework 1: ____ | Framework 2: ____ |
|---|---|---|
| Setup complexity | | |
| Metrics available | | |
| CI/CD integration | | |
| Kết quả trên cùng dataset | | |
| Insight rút ra | | |

- Scores có nhất quán không?
- Framework nào strict hơn và vì sao?
- Hai framework có tìm ra cùng failure cases không?

> *Phân tích:*

### Exercise 3.5 — Retrieval Reranking (Bonus +5)

Mục tiêu: kiểm tra việc đổi thứ tự chunks có tăng Context Precision mà không
thay đổi Context Recall hay không.

1. Chọn ít nhất 5 cases từ `artifacts/actual_answers.json`.
2. Tính Context Recall và Context Precision trước rerank.
3. Implement `rerank_by_overlap()` hoặc một reranker khác.
4. Rerank cùng tập chunks, không thêm hoặc xóa chunk.
5. Tính lại hai metrics và giải thích kết quả.

| ID | Recall before | Recall after | Precision before | Precision after | Delta Precision |
|---|---:|---:|---:|---:|---:|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| **Avg** | | | | | |

**Tại sao Recall dự kiến không đổi?**

> *Câu trả lời:*

**Khi nào reranking không đủ và cần sửa retriever/query/chunking?**

> *Câu trả lời:*

---

## Part 4 — Reflection (11:35–11:50)

Hoàn thành `reflection.md` bằng kết quả thật từ Exercise 3.2.

---

## Completion Checklist

Hoàn thành kiểm tra cuối trong khoảng 11:50–12:00.

- [ ] Tất cả required tests pass.
- [ ] `golden_dataset.json` validate thành công.
- [ ] Exercise 3.1 hoàn thành trong file JSON và bảng kết quả phía trên.
- [ ] Exercise 3.2 có năm metrics, aggregate report và ba cases thấp nhất.
- [ ] Exercise 3.3 có rubric 1–5 và bias controls.
- [ ] `reflection.md` có ba failure analyses và regression strategy.
- [ ] Đã copy `template.py` thành `solution/solution.py`.
- [ ] Exercise 3.4 và 3.5 chỉ làm nếu chọn bonus.

# Day 14 — Exercises

## AI Evaluation & Benchmarking · Lab Worksheet

**Thời gian làm bài:** 14:15–17:00

**Domain:** OrbitTech Store Customer Support

Điền trực tiếp câu trả lời vào file này. Golden dataset 20 QA được viết một lần
duy nhất trong `golden_dataset.json`, không chép lại toàn bộ vào Markdown.

---

Từ 14:15–14:30, cài môi trường và chạy baseline tests theo `guide_lab.md`.

---

## Part 1 — Warm-up (14:30–14:45)

### Exercise 1.1 — RAGAS Metric Thresholds

Theo bài giảng:

- 0.8–1.0: Good — monitor, maintain.
- 0.6–0.8: Needs work — analyze failures, iterate.
- Dưới 0.6: Significant issues — investigate.

Với từng metric, xác định khi nào score thấp có thể chấp nhận và khi nào là
critical.

| Metric | Acceptable Low Score Scenario | Critical Low Score Scenario | Action Required |
|---|---|---|---|
| Faithfulness | Answer paraphrase lại context bằng từ khác, hoặc là refusal đúng cho câu out-of-scope (A-cases) — answer ít token trùng context nên heuristic overlap chấm thấp dù answer vẫn grounded. | Answer nêu con số/điều kiện chính sách không có trong context: "restocking fee 5%", "bảo hành 3 năm", "hoàn tiền trong 24h". Customer hành động theo policy bịa → rủi ro tài chính và pháp lý. | Critical: block deploy. Bắt mọi claim có số/ngày phải cite `doc_id`, thêm grounding check trước khi trả lời, đối chiếu lại retrieval của case đó. |
| Answer Relevance | Question dài, nhiều narrative ("mình mua laptop tháng trước cho con gái và...") nhưng answer đúng lại ngắn gọn → overlap với question thấp một cách hợp lý. | Answer trả lời sang policy khác với policy được hỏi: hỏi return window nhưng trả lời warranty. User nhận hướng dẫn sai mà vẫn tưởng đúng. | Critical: sửa intent routing và prompt, bắt answer restate câu hỏi trước khi trả lời, thêm few-shot cho direct answering. |
| Context Recall | Expected answer chứa câu chữ tổng hợp/boilerplate không nằm nguyên văn trong chunk, hoặc câu multi-doc mà một doc đã đủ cho claim chính. | Retriever bỏ sót đúng doc chứa rule quyết định — ví dụ ngoại lệ hygiene accessories trong `OT-05` hoặc rule effective_date trong `OT-09`. Generator không thể trả lời đúng dù prompt tốt tới đâu. | Critical: sửa retrieval trước, không sửa prompt. Xem lại chunking, tăng top-k, query rewriting/expansion, hybrid search; thêm test coverage theo `doc_id`. |
| Context Precision | Recall cao và answer đúng, chunk relevant chỉ đứng thứ 3 thay vì thứ 1. Chi phí là token và latency, không phải correctness. | Chunk relevant rơi xuống dưới cutoff của generator, hoặc chunk của policy version cũ (`status: superseded`) xếp trên bản `current` → answer grounded vào version sai. | Cao: thêm reranker (Exercise 3.5), tinh chỉnh k, filter chunk theo `status`/`effective_date` trước khi đưa vào prompt. |
| Completeness | Expected answer viết dài kèm lý do và citation, answer ngắn nhưng đã nêu đúng fact quyết định → denominator bị thổi lên làm score thấp. | Answer bỏ mất điều kiện/ngoại lệ làm đổi quyết định của customer: nói "trả hàng trong 30 ngày" mà không nói phải *unopened*, còn opened chỉ 14 ngày và mất 10% restocking fee. Nửa sự thật nguy hiểm hơn từ chối trả lời. | Cao: đưa checklist bắt buộc (điều kiện, ngoại lệ, effective date) vào prompt, tăng context window/top-k, few-shot bằng answer đầy đủ điều kiện. |

### Exercise 1.2 — Bias trong LLM-as-a-Judge

Ba bias thường gặp:

- Position bias: judge ưu tiên answer xuất hiện trước.
- Verbosity bias: judge ưu tiên answer dài hơn.
- Self-preference: judge ưu tiên output giống chính model đó.

**Câu 1: Thiết kế experiment phát hiện position bias với ít nhất hai conditions.**

> *Câu trả lời:* Dùng **counterbalanced design** trên cùng một tập cặp answer.
> Lấy N = 50 câu hỏi OrbitTech, mỗi câu có hai answer A và B (A từ RAG hiện tại,
> B từ prompt variant). Giữ cố định judge model, rubric, temperature = 0.
>
> - **Condition 1:** trình bày theo thứ tự (A, B).
> - **Condition 2:** trình bày đúng cặp đó theo thứ tự (B, A).
> - **Condition 3 (control):** trình bày (A, A) — hai answer giống hệt nhau.
>
> Đo ba đại lượng:
>
> 1. `win_rate_position_1` trong mỗi condition. Judge không bias thì tổng win
>    rate của A ở Condition 1 và Condition 2 phải xấp xỉ nhau; nếu slot đầu
>    thắng ở cả hai condition thì bias nằm ở vị trí, không nằm ở nội dung.
> 2. **Flip rate:** tỉ lệ cặp đổi verdict khi đảo thứ tự. Flip rate cao =
>    verdict phụ thuộc vị trí chứ không phụ thuộc chất lượng.
> 3. Condition 3 là bằng chứng sạch nhất: hai answer y hệt nhau nên mọi kết quả
>    khác "tie" đều là position bias thuần túy.
>
> Kiểm định bằng McNemar test trên các cặp flip, báo cáo p-value và CI. Nếu có
> bias, fix bằng cách chấm điểm từng answer độc lập theo thang tuyệt đối 1–5
> thay vì so sánh cặp, hoặc lấy trung bình score của hai thứ tự.

**Câu 2: Làm thế nào giảm verbosity bias bằng rubric design?**

> *Câu trả lời:* Thiết kế rubric sao cho điểm gắn với **nội dung bắt buộc**, không
> gắn với ấn tượng tổng thể:
>
> - Với mỗi câu hỏi, định nghĩa trước một **checklist required facts** (ví dụ câu
>   return: window 30 ngày unopened, 14 ngày opened, 10% restocking fee, ngoại lệ
>   defective). Judge phải **liệt kê fact nào có/không có trước**, rồi mới cho
>   điểm. Extract-then-score cắt phần lớn đường tắt "dài = kỹ".
> - Ghi thẳng vào rubric: *"Độ dài không phải tiêu chí. Answer nêu đủ rule và
>   ngoại lệ trong hai câu phải được điểm bằng answer mười câu cùng nội dung."*
> - Thêm một dimension đối trọng kiểu precision — **unsupported claims** — trừ
>   điểm cho mỗi claim không có trong context. Answer dài mà độn thông tin không
>   grounded sẽ bị phạt, nên dài không còn miễn phí.
> - Tách dimension nhỏ và chấm riêng (correctness, completeness, evidence,
>   safety) thay vì một điểm tổng; điểm tổng là nơi verbosity bias trốn.
> - Kiểm chứng: chạy cùng nội dung answer ở hai phiên bản ngắn/dài (thêm câu
>   khách sáo, không thêm fact). Chênh lệch điểm giữa hai phiên bản chính là
>   verbosity bias còn lại.

**Câu 3: Tại sao cần calibrate LLM judge với human labels?**

> *Câu trả lời:* Judge score chỉ là **proxy metric**; nếu không đối chiếu với
> human label thì không biết "4/5" của judge có nghĩa gì đối với chuyên gia
> domain.
>
> - **Đo agreement:** chấm human trên một stratified subset (khoảng 20–30 case,
>   trải đủ Easy/Medium/Hard/Adversarial), tính Cohen's kappa hoặc Spearman
>   correlation giữa judge và human. Agreement thấp nghĩa là mọi kết luận rút ra
>   từ judge đều không tin được.
> - **Đặt threshold có căn cứ:** CI/CD chặn deploy theo một con số cụ thể. Chỉ
>   calibration mới cho biết ngưỡng 0.7 tương ứng "chấp nhận được" hay đã lọt
>   answer sai chính sách.
> - **Bắt lỗi domain judge không tự thấy:** dùng sai policy version, thiếu điều
>   kiện effective date, hoặc hứa exception mà `OT-00` cấm — judge dễ chấm cao vì
>   answer nghe trôi chảy.
> - **Phát hiện drift:** khi đổi judge model hoặc provider cập nhật model, điểm
>   có thể dịch chuyển trong khi hệ thống không đổi. Bộ human label giữ vai trò
>   mốc cố định để so sánh giữa các lần chạy.

### Exercise 1.3 — Evaluation trong CI/CD

**Câu 1: Chọn threshold để block deployment.**

| Metric | Threshold | Lý do |
|---|---:|---|
| Faithfulness | 0.70 | Theo bài giảng, agent có faithfulness < 0.7 không được deploy. Với customer support, hallucination là failure đắt nhất: customer hành động theo điều khoản refund/warranty bịa ra. Đây là **hard gate**, không cho override bằng lý do "chỉ thấp một chút". |
| Answer Relevance | 0.65 | Answer lệch chủ đề vẫn có thể được user sửa bằng follow-up nên chi phí thấp hơn hallucination, nhưng dưới 0.65 nghĩa là intent routing sai có hệ thống chứ không phải nhiễu từng case. |
| Completeness | 0.60 | Expected answer trong lab viết đầy đủ điều kiện và ngoại lệ nên heuristic overlap luôn chấm thấp hơn thực tế; 0.60 đúng biên "significant issues" của bài giảng. Vùng 0.60–0.70 vẫn deploy được nhưng phải mở ticket theo dõi. |

Gate chỉ pass khi đủ **cả ba** điều kiện, không chỉ ngưỡng tuyệt đối:

1. Cả ba average metric đạt threshold ở trên trên toàn bộ 20 case golden set.
2. Không metric nào giảm quá 0.05 so với baseline (regression rule của Task 4).
3. Không case adversarial nào bị `failure_type = "hallucination"` — 3/3 phải từ
   chối hoặc nêu đúng giới hạn scope. Đây là gate nhị phân, không lấy trung bình.

**Câu 2: Khi nào dùng offline evaluation, online evaluation và human review?**

> *Câu trả lời:*
>
> - **Offline** — chạy trong CI trên golden set 20 QA, ở mỗi PR, mỗi lần đổi
>   prompt, đổi model, đổi tham số retrieval và mỗi lần cập nhật corpus. Ưu điểm
>   là lặp lại được, so sánh được giữa các lần chạy và đủ nhanh/rẻ để chặn merge.
>   Điểm mù: chỉ đo được đúng những gì golden set đã bao phủ.
> - **Online** — sau khi deploy, đo trên real traffic: thumbs up/down, escalation
>   rate sang human agent, tỉ lệ hỏi lại cùng chủ đề, latency và cost mỗi
>   conversation. Dùng để phát hiện distribution shift, tức là câu hỏi thật lệch
>   khỏi golden set (mùa khuyến mãi, sản phẩm mới, policy vừa đổi effective date).
>   Chạy liên tục, sample log để chấm tự động, alert theo tuần.
> - **Human review** — dùng cho phần high-stakes và cho calibration, không dùng
>   đại trà vì đắt: các case từ chối bảo hành/hoàn tiền, case privacy và
>   security, case prompt injection, cộng thêm một stratified sample định kỳ để
>   calibrate LLM judge (Exercise 1.2 câu 3). Cũng là trọng tài khi offline metric
>   nói pass nhưng user feedback online nói fail.
>
> Ba lớp này bổ sung nhau: offline chặn regression trước khi ra production, online
> phát hiện vấn đề mà golden set chưa nghĩ tới, human review định nghĩa "đúng" để
> hai lớp tự động kia bám theo. Case mới phát hiện từ online và human review được
> đưa ngược vào golden set — đúng vòng Evaluate → Analyze → Improve → Augment.

---

## Part 2 — Core Coding (14:45–15:40)

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

## Part 3 — Golden Dataset & Real Benchmark (15:40–16:35)

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

Thiết kế rubric domain-specific cho OrbitTech Customer Support. Mỗi mức phải
đủ cụ thể để hai người chấm độc lập có thể hiểu giống nhau.

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

## Part 4 — Reflection (16:35–16:50)

Hoàn thành `reflection.md` bằng kết quả thật từ Exercise 3.2.

---

## Completion Checklist

Hoàn thành kiểm tra cuối trong khoảng 16:50–17:00.

- [ ] Tất cả required tests pass.
- [ ] `golden_dataset.json` validate thành công.
- [ ] Exercise 3.1 hoàn thành trong file JSON và bảng kết quả phía trên.
- [ ] Exercise 3.2 có năm metrics, aggregate report và ba cases thấp nhất.
- [ ] Exercise 3.3 có rubric 1–5 và bias controls.
- [ ] `reflection.md` có ba failure analyses và regression strategy.
- [ ] Đã copy `template.py` thành `solution/solution.py`.
- [ ] Exercise 3.4 và 3.5 chỉ làm nếu chọn bonus.

# Group Report — Day 06 Data Lab (Field-to-Release PoC)

## 00 · Header

| Mục | Giá trị |
|---|---|
| Group ID | <điền từ configs/lab.yaml> |
| Challenge | T09 · Multi-Market Privacy Decision Gate |
| Thành viên + vai trò | Làm cá nhân: Nguyễn Thị Hồng Hạnh (Walnut) đảm nhiệm toàn bộ vai trò Lead, Data, Core algorithm, QA/metric, Review + report |
| Git URL | https://github.com/walnut1712/K5-Day6-L2B-NguyenThiHongHanh-2a302603272-DataGovernanceAndPrivacy |
| Tag `demo-180m` (commit) | <điền sau khi tag> |
| Tag `final-24h` (commit) | <điền sau khi tag> |

## 01 · Problem & decision

- Đầu vào → đầu ra: 12 case đa thị trường (`CASE-XX.json`) → quyết định GO / HOLD / REWORK kèm `reason_codes`, `rule_ids`, `source_refs`, `risk_flags`, `policy_version`, `review_required`.
- Tiêu chí: HOLD khi có rủi ro cần DPO/legal xem xét (thiếu căn cứ hợp pháp, chuyển dữ liệu xuyên biên giới thiếu cơ chế/đánh giá, thiếu DPIA, lưu thô trên cloud, không mã hóa, có thể có trẻ vị thành niên, mơ hồ pháp lý); REWORK khi sửa được bằng bổ sung hồ sơ/thiết kế (notice, consent không hợp lệ, retention); GO khi không rule nào khớp. Precedence cố định: HOLD > REWORK > GO.
- Giả định (cần DPO/legal xác nhận): bộ rule là heuristic học tập; rule VN, SG và R-US-02 chưa đối chiếu văn bản gốc, `confidence` thấp/trung bình, `needs_legal_review: true`. Đây là tình huống giả định, không phải tư vấn pháp lý.

## 02 · Data & provenance

| Split | N | Nguồn / link | License | Synthetic? |
|---|---|---|---|---|
| dev (CASE-01..08) | 8 | `fixtures/t09_privacy_gate/` | CC0 | có |
| eval (CASE-09..12) | 4 | `fixtures/t09_privacy_gate/` | CC0 | có |

- Seed: 42. Split theo thiết kế của đề (dev 01–08, eval 09–12).
- `manifest.csv` verified (sha256): có — `python -m tools.verify_manifests` (preflight 0 FAIL sau khi sửa CRLF bằng checkout lại fixtures).
- Không dùng dữ liệu thật.

## 03 · Research & design

- Tham chiếu: Luật BVDLCN 91/2025/QH15 và NĐ 356/2025; GDPR Chương V, Điều 6, Điều 35; CCPA/CPRA; PDPA Singapore; DPDP Ấn Độ (hiệu lực 13/05/2027, ghi nhận là luật sắp hiệu lực). Chọn policy engine khai báo (YAML có version và nguồn) thay vì hard-code luật trong code để kiểm toán được từng quyết định.
- Data flow: `load` (kiểm hash manifest) → `process` (`privacy_gate.decide_case`, biểu thức `when` phân tích bằng `ast`, không `eval`) → `rank` (top-B = 12) → `review` (đọc `review_queue_reviewed.csv`, áp quyết định, ghi `audit_log.jsonl`) → `decide` (GO/HOLD/REWORK + reason_code + owner).
- Thành phần offline: chỉ PyYAML/pandas, không model, không network.
- Trade-off: rule đơn giản dễ kiểm toán nhưng không bắt được tương tác giữa các điều kiện; thị trường chưa có rule bị gắn cờ `NO_MARKET_RULES` thay vì mặc định GO.

## 04 · Baseline vs PoC

- Baseline chính (`src.examples.t09_consent_baseline`): GO nếu có consent hoặc căn cứ khác `unknown`. Cố ý sai để chứng minh checklist chỉ dựa vào consent là không đủ.
- Baseline tầm thường (`src.examples.t09_hold_all_baseline`): HOLD tất cả.
- PoC (`src.pipeline` + `configs/policy_t09.yaml`, `policy_version: group-0.2`).
- Cùng pool 12 case, cùng seed 42, không có budget khác biệt: xác nhận.
- Không có `gt/` trong repo học viên nên `src.evaluate` và `src.compare` không chạy được ở đây; số dưới đây là **tự kiểm** theo nhãn nhóm tự gán (`reports/table_per_case.csv`, `reports/selfcheck_metrics.csv`), không phải điểm chính thức của giảng viên.

**Bảng 1 · Baseline vs PoC (tự kiểm, Wilson 95%)**

| Split | Run | Critical-miss (lower tốt) | False HOLD (guardrail ≤ 0,5) |
|---|---|---|---|
| dev (7 rủi ro, 1 an toàn) | consent baseline | 6/7 [0,49–0,97] | 0/1 |
| dev | HOLD-all | 0/7 [0,00–0,35] | 1/1 — FAIL guardrail |
| dev | PoC | 0/7 [0,00–0,35] | 0/1 |
| eval (3 rủi ro, 1 an toàn) | consent baseline | 3/3 [0,44–1,00] | 0/1 |
| eval | HOLD-all | 0/3 [0,00–0,56] | 1/1 — FAIL guardrail |
| eval | PoC | 0/3 [0,00–0,56] | 0/1 |
| all (10 rủi ro, 2 an toàn) | consent baseline | 9/10 [0,60–0,98] | 0/2 |
| all | HOLD-all | 0/10 [0,00–0,28] | 2/2 — FAIL guardrail |
| all | PoC | 0/10 [0,00–0,28] | 0/2 [0,00–0,66] |

HOLD-all đạt critical-miss 0 nhưng fail guardrail nên primary của nó không hợp lệ. Runtime: xem `run_info.json` của từng run (khoảng 0,03 giây cho 12 case, CPU).

## 05 · Evaluation protocol

- Primary: Critical-miss Rate = case rủi ro bị cho GO / tổng case rủi ro (lower tốt), đơn vị là case. Guardrail: false HOLD ≤ 0,5. Ghép theo `case_id`; case thiếu tính là GO (xem `reports/metric_contract.md`).
- Nhãn rủi ro do nhóm tự gán bằng cách đọc từng case; không phải gold của giảng viên.
- Độ bất định: khoảng Wilson 95% vì N rất nhỏ; báo từng case ở `reports/table_per_case.csv`.
- Lệnh evaluate chính thức do giảng viên chạy: `python -m src.evaluate --track t09 --pred out/poc/decisions.csv` (cần `gt/`; ở repo học viên trả exit 2).

## 06 · Result slices

| Slice | N | Consent baseline | PoC | Ghi chú |
|---|---|---|---|---|
| Chuyển dữ liệu xuyên biên giới (CASE-02, 07, 10) | 3 | GO cả 3 | HOLD 02 và 07; GO 10 | CASE-10 có adequacy, TIA, LIA, DPIA nên GO hợp lý |
| Thị trường VN (01, 03, 07, 12) | 4 | GO cả 4 | HOLD cả 4 | không có căn cứ lợi ích hợp pháp ở VN |
| dev so với eval | 8 / 4 | xem Bảng 1 | xem Bảng 1 | PoC thiết kế trên dev |

- **Failure case 1 (bắt buộc của T09):** kết luận hợp pháp chỉ dựa vào consent bỏ sót chuyển dữ liệu xuyên biên giới. CASE-02 (EU, `transfer.mechanism = null`) và CASE-07 (VN, chưa có `transfer_impact_assessment`) đều bị baseline cho GO. Root cause: baseline không đọc trường `transfer`. PoC bắt bằng R-XB-01 và R-VN-02, `risk_flags` có `CROSS_BORDER_TRANSFER`.
- **Failure case 2 (điểm yếu của chính PoC):** CASE-06 (SG) ban đầu GO vì không có rule SG nào, tức GO do thiếu luật chứ không phải đã kiểm chứng. CASE-11 chỉ HOLD nhờ `ambiguity_notes`, không rule nào xét `precise_location`. Xử lý: thêm rule SG và R-US-02, thêm cờ `NO_MARKET_RULES`, và reviewer `escalate` CASE-06. Các rule này thêm sau khi quan sát CASE-06 và CASE-11, số điều khoản chưa đối chiếu văn bản gốc.
- Latency: khoảng 0,03 giây cho 12 case; máy/CPU: <điền>.

## 07 · Human & decision

- Review queue: `out/poc/review_queue.csv`, B = 12 (mọi case), xếp theo `score` (HOLD 1,0; REWORK 0,7; GO 0).
- Override và audit: reviewer điền `reviewer`, `reviewer_decision` (approve/escalate/edit/reject/skip), `review_note` trong `review_queue_reviewed.csv`; pipeline áp quyết định và ghi `audit_log.jsonl` (12 sự kiện, có before/after và lý do). `approve` giữ nguyên, `escalate` ép `review_required=True`, `edit`/`reject` đổi quyết định theo `override_value`. Kết quả: CASE-06, 09, 11 được escalate; các case còn lại approve.
- Policy quyết định kèm `reason_code` và `owner` ở `out/poc/decision.json`. Mọi HOLD/REWORK đều cần DPO/legal xem xét; hệ thống chỉ hỗ trợ rà soát, quyết định cuối thuộc người phụ trách.

## 08 · Reproduce & tests

```powershell
python -m venv .venv ; .venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m src.main --track t09 --output out/poc --run-name poc --offline --seed 42
.venv\Scripts\python.exe -m src.main --track t09 --pipeline src.examples.t09_consent_baseline --output out/baseline --run-name baseline --offline --seed 42
.venv\Scripts\python.exe -m src.main --track t09 --pipeline src.examples.t09_hold_all_baseline --output out/baseline_hold_all --run-name baseline_hold_all --offline --seed 42
.venv\Scripts\python.exe -m pytest -q
```

- `pytest -q`: 0 failed (các test cần `gt/` được skip theo thiết kế); 6 test của nhóm trong `tests/test_t09_team.py` (success và failure/edge).
- Python 3.13.17, Windows; git sha: <điền>.
- Lưu ý: `audit_log.jsonl` là append-only nên cần xóa trước khi chạy lại PoC.

## 09 · Limitations & ethics

- Chỉ dùng dữ liệu synthetic, không có PII thật.
- Nhãn tự gán sau khi đã xem output của cả 12 case, kể cả eval; N = 4 ở eval với 1 case an toàn nên false HOLD gần như không đo được; PoC được thiết kế trên dev nên không chứng minh khả năng tổng quát hóa.
- Bộ rule là heuristic, chưa kiểm chứng pháp lý; nếu scale 10 lần cần quản lý rule theo thị trường và phiên bản, kiểm thử hồi quy.
- Không tuyên bố đạt GDPR hay luật Việt Nam; mọi giả định cần DPO/legal xác nhận. CASE-09 (DPDP Ấn Độ từ 13/05/2027) chỉ ghi chú là luật sắp hiệu lực, không coi là vi phạm hiện tại.
- Cải tiến: đối chiếu số điều khoản với văn bản gốc, thêm rule cho IN, xét `data_types` nhạy cảm theo từng thị trường.

## 10 · Team contribution

Lab làm cá nhân. Hai tác giả còn lại trong `git shortlog` là commit có sẵn từ repo template, không phải thành viên nhóm (xem `reports/team_contributions.csv`).

| Học viên | Git author/email | Module / vai trò | Commit SHA | Trình bày? |
|---|---|---|---|---|
| Nguyễn Thị Hồng Hạnh | Walnut / s4020232@rmit.edu.vn | Toàn bộ: policy engine, baseline, review, audit, tests, report | <điền> | có |

## 11 · References

| URL | Ngày xem | Ý nghĩa |
|---|---|---|
| https://eur-lex.europa.eu/eli/reg/2016/679/oj | 2026-11-14 | GDPR: Chương V (chuyển dữ liệu), Điều 6 (căn cứ), Điều 35 (DPIA) |
| https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Luat-Bao-ve-du-lieu-ca-nhan-2025-so-91-2025-QH15-625628.aspx | 2026-11-14 | Luật BVDLCN 91/2025: consent, đánh giá tác động, chuyển dữ liệu |

---

**Bảng 3 · Checklist chốt khi nộp**

- [x] Input mẫu không chứa PII thật.
- [x] 1 lệnh run, 1 lệnh evaluate (giảng viên chạy), 1 lệnh tests; chạy offline.
- [x] Có baseline và PoC, 2 failure case, reviewer evidence, decision log.
- [ ] Tag cuối cùng và SHA trong header.
- [x] Tự kiểm có khoảng tin cậy; không có gold của giảng viên.

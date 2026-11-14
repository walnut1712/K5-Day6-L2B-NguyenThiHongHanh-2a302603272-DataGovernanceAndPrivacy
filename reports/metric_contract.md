# Metric contract (khai báo bắt buộc — chốt trước khi chạy eval)

> Các metric chuẩn đã được cài trong `src/metrics/tracks.py`. File này là nơi nhóm **cam kết** cách dùng chúng.
> Không đổi testset, threshold hay trọng số sau khi đã thấy kết quả eval.

| Mục | Khai báo của nhóm |
|---|---|
| Track | T09 · Multi-Market Privacy Decision Gate |
| Primary metric (tên đúng như evaluator in ra) | Critical-miss Rate (`eval_t09`), split `eval` |
| Tăng tốt hay giảm tốt? | **lower** (giảm = tốt) |
| Đơn vị đánh giá | case (mỗi `CASE-XX.json` là 1 đơn vị) |
| Công thức + numerator / denominator | Numerator = số case rủi ro (theo gold của giảng viên) bị cho `GO`. Denominator = tổng số case rủi ro trong split. Tương đương 1 − High-risk HOLD Recall. |
| Cách ghép prediction ↔ GT | Theo `case_id`. Case thiếu trong `decisions.csv` được tính là `GO` (worst case). |
| Candidate pool cố định | 12 case của `fixtures/t09_privacy_gate/` (CASE-01..12), không thêm bớt |
| Review budget B / K | Không phải bài toán xếp hạng top-K. Mọi case có `decision ∈ {HOLD, REWORK}` hoặc `review_required=True` đều vào review queue để người phụ trách (DPO/legal giả định) duyệt cuối. |
| Seed | 42 |
| Threshold policy (chọn trên dev như thế nào) | Không có threshold học từ dữ liệu. Quyết định do rule trong file policy có version và nguồn (`configs/policy_t09.yaml`). Ngưỡng duy nhất là retention > 365 ngày, lấy nguyên từ rule mẫu của đề (teaching threshold). Rule được thiết kế từ văn bản luật và 8 case dev (CASE-01..08). Precedence cố định: HOLD > REWORK > GO. |
| Eval split (không dùng để tune) | `eval` = CASE-09..12 (N=4), là số chính thức. Dev = CASE-01..08 chỉ dùng để thiết kế và kiểm rule. `--split all` chỉ để tự kiểm. |
| Chỉ số lỗi xấu | **Miss** = case rủi ro bị cho GO (critical miss, lỗi nghiêm trọng nhất). **False alarm** = case an toàn bị HOLD (false HOLD rate, guardrail ≤ 0.5). Primary chỉ hợp lệ khi guardrail PASS. |
| Slices sẽ báo cáo (≥2) | (1) theo thị trường: VN / EU / US-CA / SG / IN. (2) theo loại rủi ro: chuyển dữ liệu xuyên biên giới (CASE-02, 07, 10) so với còn lại. (3) dev so với eval. |
| Cách báo độ bất định khi N nhỏ | N=4 nên báo **từng case** kèm khoảng tin cậy Wilson 95% cho critical-miss và false HOLD. Không diễn giải phần trăm như số ổn định. |
| Ngày giờ chốt + người chốt | 2026-11-14, [giờ] · [tên người chốt] |

## Baseline (khai báo cùng contract)
- **Baseline chính** (`src.examples.t09_consent_baseline`): GO nếu có consent hoặc lawful basis khác `unknown`. Sai có chủ ý, dùng để chứng minh checklist chỉ dựa vào consent là không đủ.
- **Baseline tầm thường** (`src.baseline_hold_all`): HOLD tất cả. Critical-miss = 0 nhưng false HOLD cao, kỳ vọng FAIL guardrail. Báo cáo cả hai.
- Nếu baseline = 0 thì ghi rõ "baseline = 0" thay vì phần trăm cải thiện.

## Metric phụ
False HOLD rate, exact decision accuracy, reason-code match, audit trace completeness (đủ `rule_ids`, `source_refs`, `policy_version`).

## Giới hạn trung thực
- Nhóm **không có `gt/`**. Việc nhóm đánh dấu case nào rủi ro trên dev là tự gán nhãn, không phải gold của giảng viên.
- Các file `CASE-09..12` nằm trong fixtures nên đọc được. Nhóm đã xem output của PoC trên cả 12 case. Mọi rule thêm hoặc sửa **sau khi quan sát case eval** (ví dụ rule `precise_location` cho CASE-11, rule SG) phải ghi nguồn luật và ghi chú riêng trong report, để người chấm tự đánh giá.
- Bộ rule là heuristic học tập, chưa kiểm chứng pháp lý. HOLD/REWORK cần DPO/legal xem xét. Không tuyên bố "đạt GDPR / luật Việt Nam".
- Case có luật sắp hiệu lực (CASE-09, DPDP Ấn Độ từ 13/05/2027) chỉ ghi chú, không coi là vi phạm hiện tại.
# app.py
import streamlit as st
import pandas as pd
import numpy as np
import json
import math
import os

# Optional: OpenAI for NLP explanations (tùy chọn)
USE_OPENAI = True
try:
    import openai
    from dotenv import load_dotenv
    load_dotenv()
    if os.getenv("OPENAI_API_KEY"):
        openai.api_key = os.getenv("OPENAI_API_KEY")
    else:
        # nếu không có API key thì tắt
        USE_OPENAI = False
except Exception:
    USE_OPENAI = False

# ---------- Helper functions ----------
def load_products(path="loan_products.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def monthly_payment(principal, annual_rate_percent, months, method="annuity"):
    """
    Trả về payment hàng tháng theo lãi suất hàng năm (phần trăm).
    method: "annuity" (nộp đều) hoặc "flat" (lãi theo dư nợ ban đầu - mô phỏng)
    """
    if months <= 0:
        return 0.0
    r = annual_rate_percent / 100.0 / 12.0  # monthly rate decimal
    if method == "annuity":
        if r == 0:
            return principal / months
        payment = principal * r / (1 - (1 + r) ** (-months))
        return payment
    elif method == "flat":
        # simple flat: monthly = principal/months + (principal * annual_rate_percent/100)/12
        monthly_interest = principal * (annual_rate_percent / 100.0) / 12.0
        return principal / months + monthly_interest
    else:
        raise ValueError("Unknown method")

def amortization_schedule(principal, annual_rate_percent, months):
    r = annual_rate_percent / 100.0 / 12.0
    payment = monthly_payment(principal, annual_rate_percent, months, method="annuity")
    schedule = []
    remaining = principal
    for m in range(1, months + 1):
        interest = remaining * r
        principal_paid = payment - interest
        remaining = remaining - principal_paid
        schedule.append({
            "month": m,
            "payment": round(payment, 2),
            "interest": round(interest, 2),
            "principal_paid": round(principal_paid, 2),
            "remaining": round(max(0.0, remaining), 2)
        })
    return pd.DataFrame(schedule)

def eligibility_check(monthly_income, monthly_payment_amount, min_income, dti_threshold=0.4):
    """
    DTI threshold: tối đa phần trăm thu nhập dành cho trả nợ (ví dụ 0.4 = 40%)
    """
    dti = monthly_payment_amount / monthly_income if monthly_income > 0 else 1.0
    pass_dti = dti <= dti_threshold
    pass_min_income = monthly_income >= min_income
    return {
        "monthly_income": monthly_income,
        "monthly_payment": monthly_payment_amount,
        "dti": dti,
        "pass_dti": pass_dti,
        "pass_min_income": pass_min_income
    }

def explain_with_openai(system_prompt, user_prompt):
    if not USE_OPENAI:
        return "OpenAI API key not provided or disabled. Chọn 'Use OpenAI' và thiết lập OPENAI_API_KEY để bật tính năng diễn giải ngôn ngữ tự nhiên."
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini", # or "gpt-4o" or another model you have access to
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"OpenAI error: {str(e)}"

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Loan Advisor Bot (Agribank - Demo)", layout="wide")
st.title("Chatbot tư vấn tín dụng — Mô phỏng Agribank")

st.sidebar.header("Thiết lập")
products = load_products()
product_map = {p["name"]: p for p in products}
product_names = list(product_map.keys())
selected_name = st.sidebar.selectbox("Chọn gói vay (mô phỏng)", product_names)
product = product_map[selected_name]

principal = st.sidebar.number_input("Số tiền vay (VND)", min_value=0, value=100_000_000, step=1_000_000, format="%d")
term_months = st.sidebar.number_input("Kỳ hạn (tháng)", min_value=1, value=60, step=1)
monthly_income = st.sidebar.number_input("Thu nhập hàng tháng (VND)", min_value=0, value=20_000_000, step=100_000, format="%d")
repayment_method = st.sidebar.selectbox("Phương thức trả nợ", ["annuity (trả đều)", "flat (trả gốc + lãi cố định)"])
use_openai = st.sidebar.checkbox("Use OpenAI để diễn giải lời tư vấn (tùy chọn)", value=False)

st.header("Thông tin gói vay (mô phỏng)")
st.write(f"**{product['name']}** — Lãi suất hàng năm (mô phỏng): **{product['annual_rate_percent']}%**")
st.write(f"Khoảng: {product['min_amount']:,} VND — {product['max_amount']:,} VND")
st.write(f"Kỳ hạn tối thiểu/tối đa: {product['min_term_months']} tháng / {product['max_term_months']} tháng")
st.write("Hồ sơ bắt buộc (mô phỏng): " + ", ".join(product.get("required_documents", [])))

# Validate inputs vs product
errors = []
if principal < product["min_amount"] or principal > product["max_amount"]:
    errors.append("Số tiền vay nằm ngoài phạm vi gói vay.")
if term_months < product["min_term_months"] or term_months > product["max_term_months"]:
    errors.append("Kỳ hạn nằm ngoài phạm vi gói vay.")
if monthly_income < 0:
    errors.append("Thu nhập không hợp lệ.")

if errors:
    st.error(" / ".join(errors))

# Compute payment
monthly = monthly_payment(principal, product["annual_rate_percent"], int(term_months),
                          method="annuity" if repayment_method.startswith("annuity") else "flat")
st.subheader("Kết quả mô phỏng")
st.write(f"- Thanh toán hàng tháng (ước tính): **{round(monthly):,} VND**")
st.write(f"- Tổng số tiền phải trả (approx): **{round(monthly*term_months):,} VND**")
st.write(f"- Tổng lãi ước tính: **{round(monthly*term_months - principal):,} VND**")

# Eligibility check (DTI)
elig = eligibility_check(monthly_income, monthly, product["min_monthly_income"], dti_threshold=0.4)
st.subheader("Kiểm tra điều kiện cơ bản")
st.write(f"- Tỷ lệ trả nợ trên thu nhập (DTI): **{elig['dti']*100:.1f}%** (ngưỡng mặc định: 40%)")
st.write(f"- Thu nhập tối thiểu yêu cầu: **{product['min_monthly_income']:,} VND**")
st.write(f"- Kết luận DTI hợp lệ? **{elig['pass_dti']}**")
st.write(f"- Thu nhập tối thiểu đạt? **{elig['pass_min_income']}**")

if not (elig['pass_dti'] and elig['pass_min_income']):
    st.warning("KHÔNG đạt điều kiện tối thiểu theo quy tắc mô phỏng. Vui lòng điều chỉnh số liệu hoặc chọn gói khác.")

# Show amortization schedule button
if st.button("Hiện bảng trả nợ (amortization schedule)"):
    df_schedule = amortization_schedule(principal, product["annual_rate_percent"], int(term_months))
    st.dataframe(df_schedule)

# Chat-like advisor: người dùng mô tả yêu cầu -> bot trả lời (cơ bản)
st.subheader("Chat tư vấn (mô phỏng)")
user_input = st.text_area("Nhập câu hỏi tư vấn của khách hàng:", value="Tôi muốn vay 500 triệu trong 5 năm, thu nhập 30 triệu/tháng. Tôi có đủ điều kiện không?")

if st.button("Gửi câu hỏi"):
    # Simple rule-based answer + injection of computed numbers
    reply_lines = []
    reply_lines.append(f"Bạn hỏi: \"{user_input}\"")
    reply_lines.append("")
    reply_lines.append("Kết quả mô phỏng nhanh:")
    reply_lines.append(f"- Gói: {product['name']}")
    reply_lines.append(f"- Số tiền: {principal:,} VND; Kỳ hạn: {term_months} tháng; Lãi suất (mô phỏng): {product['annual_rate_percent']}%/năm")
    reply_lines.append(f"- Thanh toán hàng tháng ước tính: {round(monthly):,} VND")
    reply_lines.append(f"- Tỷ lệ trả nợ trên thu nhập (DTI): {elig['dti']*100:.1f}% (ngưỡng 40%)")
    if elig['pass_dti'] and elig['pass_min_income']:
        reply_lines.append("- Theo mô phỏng, bạn **có thể đáp ứng** điều kiện cơ bản về thu nhập/DTI.")
    else:
        reply_lines.append("- Theo mô phỏng, bạn **không đáp ứng** điều kiện cơ bản. Cần xem xét giảm số tiền vay hoặc kéo dài kỳ hạn, hoặc tăng thu nhập chứng minh.")
    reply_text = "\n".join(reply_lines)

    if use_openai and USE_OPENAI:
        system_prompt = "Bạn là chuyên gia tư vấn tín dụng ngân hàng. Giải thích cho khách hàng bằng tiếng Việt, rõ ràng, ngắn gọn, nêu ra các bước tiếp theo cần chuẩn bị hồ sơ."
        user_prompt = "Dữ liệu: \n" + reply_text + "\nHãy diễn giải thành lời tư vấn thân thiện, bao gồm danh sách giấy tờ cần chuẩn bị và khuyến nghị cụ thể."
        ai_answer = explain_with_openai(system_prompt, user_prompt)
        st.markdown("### Lời khuyên (do AI diễn giải):")
        st.write(ai_answer)
    else:
        st.markdown("### Lời khuyên (mô phỏng):")
        st.write(reply_text)
        st.write("- Hồ sơ cần chuẩn bị (mô phỏng): " + ", ".join(product.get("required_documents", [])))
        st.write("- Bước tiếp theo: 1) Đến chi nhánh để tư vấn chi tiết; 2) Nộp hồ sơ và sao kê thu nhập; 3) Ngân hàng thẩm định giá trị tài sản/khả năng trả nợ.")

st.info("Lưu ý: Kết quả trên là mô phỏng. Để biết quyết định chính thức, cần thẩm định bởi bộ phận tín dụng Agribank.")

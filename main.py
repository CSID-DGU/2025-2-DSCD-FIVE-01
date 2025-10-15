from openai import OpenAI
from dotenv import load_dotenv
import os
import json

# OpenAI API 키 설정
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

import re
import json

def _parse_json_safely(text: str):
    """
    1) 그대로 json.loads 시도
    2) ```json ... ``` 또는 ``` ... ``` 감싸진 경우 벗겨서 재시도
    3) 마지막으로 중괄호/대괄호 범위만 추출해서 재시도
    """
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass

    # 코드펜스 제거
    fenced = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip(), flags=re.DOTALL)
    try:
        return json.loads(fenced), None
    except json.JSONDecodeError:
        pass

    # JSON 스니펫만 추출 (가장 바깥 { ... } 또는 [ ... ])
    m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1)), None
        except json.JSONDecodeError as e:
            return None, f"JSON decode failed after extraction: {e}"
    return None, "JSON decode failed: unrecognized format"


def classify_hs_code(product_name, product_description, top_n=3):
    """
    ChatGPT API를 활용하여 HS 코드 후보 분류 및 근거/관세율/FTA 국가 정보 반환
    """
    prompt = f"""
    You are an expert customs classifier.
    Task: Given a product name and description, output the Top-{top_n} HS code candidates and why.

    Input:
    - Product Name: {product_name}
    - Product Description: {product_description}
    
    Context:
    

    Output format (strict JSON):
    {{
        "candidates": [
            {{
                "hs_code": "string",
                "reason": "why this code was chosen",
            }}
        ]
    }}
    """

    #  JSON
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a customs and HS code classification expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    output_text = response.choices[0].message.content.strip()

    # ✅ 폴백 파싱 (혹시 대비)
    result, err = _parse_json_safely(output_text)
    if err:
        result = {"error": err, "raw_output": output_text}

    return result



if __name__ == "__main__":
    product_name = "스테인리스 주방용 칼"
    product_description = "주방에서 사용하는 날이 있는 스테인리스 스틸 칼. 주로 식재료 절단에 사용."

    result = classify_hs_code(product_name, product_description, top_n=3)

    # 보기 좋게 출력
    print(json.dumps(result, indent=2, ensure_ascii=False))
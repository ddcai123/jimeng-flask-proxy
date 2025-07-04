import os
import flask
from flask import request, jsonify
import requests
import hashlib
import hmac
import datetime

app = flask.Flask(__name__)

ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
REGION = "cn-north-1"
SERVICE = "cv"
HOST = "visual.volcengineapi.com"
API_VERSION = "2022-08-31"
SUBMIT_ACTION = "CVSync2AsyncSubmitTask"
RESULT_ACTION = "CVSync2AsyncGetResult"

def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def get_signature(headers, body, action):
    t = datetime.datetime.utcnow()
    date = t.strftime('%Y%m%d')
    timestamp = t.strftime('%Y%m%dT%H%M%SZ')
    canonical_uri = "/"
    canonical_querystring = f"Action={action}&Version={API_VERSION}"
    canonical_headers = f"content-type:{headers['Content-Type']}\nhost:{HOST}\n"
    signed_headers = "content-type;host"
    payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = "POST\n" + canonical_uri + "\n" + canonical_querystring + "\n" + canonical_headers + "\n" + signed_headers + "\n" + payload_hash
    algorithm = "HMAC-SHA256"
    credential_scope = f"{date}/{REGION}/{SERVICE}/request"
    string_to_sign = algorithm + "\n" + timestamp + "\n" + credential_scope + "\n" + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    k_date = sign(("VOLC" + SECRET_KEY).encode("utf-8"), date)
    k_region = sign(k_date, REGION)
    k_service = sign(k_region, SERVICE)
    k_signing = sign(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization_header = f"{algorithm} Credential={ACCESS_KEY}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    return timestamp, authorization_header

@app.route('/generate-video', methods=['POST'])
def generate_video():
    payload = request.json
    request_body = {
        "req_key": "jimeng_vgfm_i2v_l20",
        "image_urls": payload.get("image_urls", []),
        "prompt": payload.get("prompt", ""),
        "aspect_ratio": payload.get("aspect_ratio", "16:9")
    }
    body_json = flask.json.dumps(request_body)
    headers = {
        "Content-Type": "application/json",
        "Host": HOST
    }
    
    # 获取签名
    timestamp, auth = get_signature(headers, body_json, SUBMIT_ACTION)
    headers["Authorization"] = auth
    headers["X-Date"] = timestamp

    url = f"https://{HOST}/?Action={SUBMIT_ACTION}&Version={API_VERSION}"
    
    try:
        # 请求即梦API
        resp = requests.post(url, headers=headers, data=body_json)
        resp.raise_for_status()  # 若响应状态码是4xx/5xx会抛出异常
        
        # 打印返回内容，帮助调试
        print("Response Data:", resp.json())
        
        # 返回生成请求信息和即梦的响应
        return jsonify({
            "request_body": request_body,
            "response_status": resp.status_code,
            "response_data": resp.json()
        })
    
    except requests.exceptions.HTTPError as errh:
        return jsonify({"error": f"Http Error: {str(errh)}"})
    except requests.exceptions.ConnectionError as errc:
        return jsonify({"error": f"Error Connecting: {str(errc)}"})
    except requests.exceptions.Timeout as errt:
        return jsonify({"error": f"Timeout Error: {str(errt)}"})
    except requests.exceptions.RequestException as err:
        return jsonify({"error": f"OOps: Something Else {str(err)}"})

@app.route('/get-video', methods=['POST'])
def get_video():
    payload = request.json
    task_id = payload.get("task_id")
    if not task_id:
        return jsonify({"error": "Missing task_id"}), 400

    request_body = {
        "req_key": "jimeng_vgfm_i2v_l20",
        "task_id": task_id
    }
    body_json = flask.json.dumps(request_body)
    headers = {
        "Content-Type": "application/json",
        "Host": HOST
    }
    
    timestamp, auth = get_signature(headers, body_json, RESULT_ACTION)
    headers["Authorization"] = auth
    headers["X-Date"] = timestamp
    
    url = f"https://{HOST}/?Action={RESULT_ACTION}&Version={API_VERSION}"
    
    try:
        resp = requests.post(url, headers=headers, data=body_json)
        resp.raise_for_status()  # 若响应状态码是4xx/5xx会抛出异常
        
        # 返回任务查询结果
        return jsonify(resp.json())
    
    except requests.exceptions.RequestException as err:
        return jsonify({"error": f"Request failed: {str(err)}"}), 500


if __name__ == '__main__':
     port = int(os.environ.get("PORT", 5000))
     app.run(host="0.0.0.0", port=port, debug=True)

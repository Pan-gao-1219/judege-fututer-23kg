from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import streamlit as st


DATA_DIR = Path("data")
LOCAL_DATA_PATH = DATA_DIR / "responses.jsonl"


st.set_page_config(page_title="毕业去向意向收集表", page_icon="📝", layout="centered")


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def get_github_config() -> dict[str, str]:
    return {
        "token": secret("GITHUB_TOKEN"),
        "repo": secret("GITHUB_REPO"),
        "branch": secret("GITHUB_BRANCH", "main"),
        "data_path": secret("DATA_PATH", "data/responses.jsonl"),
    }


def github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_github_file(config: dict[str, str]) -> tuple[str, str | None]:
    url = f"https://api.github.com/repos/{config['repo']}/contents/{config['data_path']}"
    response = requests.get(
        url,
        headers=github_headers(config["token"]),
        params={"ref": config["branch"]},
        timeout=15,
    )
    if response.status_code == 404:
        return "", None
    response.raise_for_status()
    payload = response.json()
    content = base64.b64decode(payload["content"]).decode("utf-8")
    return content, payload["sha"]


def save_to_github(record: dict[str, Any]) -> None:
    config = get_github_config()
    if not config["token"] or not config["repo"]:
        raise RuntimeError("请先在 Streamlit Secrets 中配置 GITHUB_TOKEN 和 GITHUB_REPO。")

    url = f"https://api.github.com/repos/{config['repo']}/contents/{config['data_path']}"
    headers = github_headers(config["token"])
    line = json.dumps(record, ensure_ascii=False)

    for attempt in range(3):
        current_content, sha = fetch_github_file(config)
        next_content = current_content
        if next_content and not next_content.endswith("\n"):
            next_content += "\n"
        next_content += line + "\n"

        body: dict[str, Any] = {
            "message": f"Add survey response from {record['name']}",
            "content": base64.b64encode(next_content.encode("utf-8")).decode("ascii"),
            "branch": config["branch"],
        }
        if sha:
            body["sha"] = sha

        response = requests.put(url, headers=headers, json=body, timeout=20)
        if response.status_code in (200, 201):
            return
        if response.status_code == 409 and attempt < 2:
            time.sleep(0.7)
            continue
        response.raise_for_status()


def save_locally(record: dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with LOCAL_DATA_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def validate(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not record["name"].strip():
        errors.append("请填写姓名。")

    if not record["student_id"].strip():
        errors.append("请填写学号。")

    if not record["can_recommend"]:
        errors.append("请选择是否具备保研资格。")

    if record["can_recommend"] == "能保研":
        if not record["recommend_destination"]:
            errors.append("请选择保研去向。")
        if record["recommend_destination"] == "保研本校" and not record["local_recommend_type"]:
            errors.append("请选择保研本校类型。")
        if record["recommend_destination"] == "保研外校" and not record["external_recommend_major"].strip():
            errors.append("请填写保研外校意向方向/专业。")

    if record["can_recommend"] == "不能保研":
        if not record["non_recommend_plan"]:
            errors.append("请选择不能保研后的选择。")
        if record["non_recommend_plan"] == "考研":
            if not record["postgraduate_school"]:
                errors.append("请选择考研学校。")
            if record["postgraduate_school"] == "本校" and not record["local_postgraduate_major"]:
                errors.append("请选择考研本校方向。")
            if record["postgraduate_school"] == "外校" and not record["external_postgraduate_major"].strip():
                errors.append("请填写考研外校具体方向/专业。")
        if record["non_recommend_plan"] == "找工作" and not record["job_intention"].strip():
            errors.append("请填写就业意向。")

    return errors


def show_admin_view() -> None:
    admin_password = secret("ADMIN_PASSWORD")
    if not admin_password:
        return

    with st.expander("管理员查看"):
        password = st.text_input("管理员密码", type="password")
        if password != admin_password:
            return

        st.info("正式部署后，原始数据保存在 GitHub 仓库的 data/responses.jsonl 文件中。")
        if LOCAL_DATA_PATH.exists():
            rows = [
                json.loads(line)
                for line in LOCAL_DATA_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            st.dataframe(rows, use_container_width=True)
        else:
            st.caption("本地暂无数据。")


st.title("毕业去向意向收集表")
st.caption("请按个人实际情况填写，提交后无需重复填写。")

if "step" not in st.session_state:
    st.session_state.step = 1

if st.session_state.step == 1:
    with st.form("basic_form", clear_on_submit=False):
        name = st.text_input("姓名", placeholder="请输入姓名")
        student_id = st.text_input("学号", placeholder="请输入学号")
        can_recommend = st.radio("是否具备保研资格？", ["能保研", "不能保研"], index=None, horizontal=True)
        next_step = st.form_submit_button("下一步")

    if next_step:
        basic_record = {
            "name": name.strip(),
            "student_id": student_id.strip(),
            "can_recommend": can_recommend,
        }
        basic_errors = []
        if not basic_record["name"]:
            basic_errors.append("请填写姓名。")
        if not basic_record["student_id"]:
            basic_errors.append("请填写学号。")
        if not basic_record["can_recommend"]:
            basic_errors.append("请选择是否具备保研资格。")

        if basic_errors:
            for error in basic_errors:
                st.error(error)
        else:
            st.session_state.basic_record = basic_record
            st.session_state.step = 2
            st.rerun()

submitted = False
record: dict[str, Any] | None = None

if st.session_state.step == 2:
    basic_record = st.session_state.basic_record
    st.info(f"{basic_record['name']}（{basic_record['student_id']}）：{basic_record['can_recommend']}")

    recommend_destination = ""
    local_recommend_type = ""
    external_recommend_major = ""
    non_recommend_plan = ""
    postgraduate_school = ""
    local_postgraduate_major = ""
    external_postgraduate_major = ""
    job_intention = ""

    if basic_record["can_recommend"] == "能保研":
        recommend_destination = st.radio("保研去向", ["保研本校", "保研外校"], index=None, horizontal=True)

        if recommend_destination == "保研本校":
            local_recommend_type = st.radio(
                "保研本校类型",
                ["工程硕博", "学硕（地质资源与地质工程）", "专硕（地质工程）"],
                index=None,
            )

        if recommend_destination == "保研外校":
            external_recommend_major = st.text_input(
                "保研外校意向方向/专业",
                placeholder="例如：地质工程、资源勘查、环境地质等",
            )

    if basic_record["can_recommend"] == "不能保研":
        non_recommend_plan = st.radio("不能保研后的选择", ["考研", "找工作"], index=None, horizontal=True)

        if non_recommend_plan == "考研":
            postgraduate_school = st.radio("考研学校选择", ["本校", "外校"], index=None, horizontal=True)

            if postgraduate_school == "本校":
                local_postgraduate_major = st.radio(
                    "考研本校方向",
                    ["地质资源与地质工程", "地质工程"],
                    index=None,
                )

            if postgraduate_school == "外校":
                external_postgraduate_major = st.text_input(
                    "考研外校具体方向/专业",
                    placeholder="请输入具体方向/专业",
                )

        if non_recommend_plan == "找工作":
            job_intention = st.text_input(
                "就业意向",
                placeholder="例如：地勘单位、国企、考公、设计院等",
            )

    submitted = st.button("提交")

    if st.button("返回修改基本信息"):
        st.session_state.step = 1
        st.rerun()

    if submitted:
        record = {
            "submitted_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "name": basic_record["name"],
            "student_id": basic_record["student_id"],
            "can_recommend": basic_record["can_recommend"],
            "recommend_destination": recommend_destination,
            "local_recommend_type": local_recommend_type,
            "external_recommend_major": external_recommend_major.strip(),
            "non_recommend_plan": non_recommend_plan,
            "postgraduate_school": postgraduate_school,
            "local_postgraduate_major": local_postgraduate_major,
            "external_postgraduate_major": external_postgraduate_major.strip(),
            "job_intention": job_intention.strip(),
        }

if submitted and record:
    validation_errors = validate(record)
    if validation_errors:
        for error in validation_errors:
            st.error(error)
    else:
        try:
            if get_github_config()["token"] and get_github_config()["repo"]:
                save_to_github(record)
            else:
                save_locally(record)
            st.success("提交成功，感谢填写。")
        except Exception as exc:
            st.error(f"提交失败：{exc}")

show_admin_view()

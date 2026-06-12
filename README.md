# 毕业去向意向收集表

这是一个 Streamlit 问卷应用，按条件分支显示问题，并把提交结果写入 GitHub 仓库的 `data/responses.jsonl`。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

本地不配置 GitHub secrets 时，数据会临时写入当前目录的 `data/responses.jsonl`。

## 部署成链接

1. 打开 Streamlit Community Cloud。
2. 选择本仓库 `Pan-gao-1219/judege-fututer-23kg`。
3. 入口文件选择 `app.py`。
4. 在 Streamlit 的 `Secrets` 中填入：

```toml
GITHUB_TOKEN = "这里填 GitHub fine-grained token"
GITHUB_REPO = "Pan-gao-1219/judege-fututer-23kg"
GITHUB_BRANCH = "main"
DATA_PATH = "data/responses.jsonl"
ADMIN_PASSWORD = "自己设置一个管理员密码"
```

## GitHub Token 权限

建议使用 GitHub fine-grained personal access token：

- Repository access：只选择这个问卷仓库
- Permissions：Contents，Read and write

不要把 token 发到聊天、代码、README 或公开仓库里，只放在 Streamlit Secrets。

## 查看数据

部署后，每次提交都会向 GitHub 仓库写入一行 JSON。你可以直接下载 `data/responses.jsonl`，也可以之后再转换成 Excel。

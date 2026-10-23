# 安装与第一次使用

这些步骤由用户的 Agent 执行。用户提供自己的内容与照片；已有本机工具、图片能力和登录配置优先复用。无需登录敏敏的网站，不向本站上传用户照片。

1. 从发行页取得 `release.json`，下载对应完整 ZIP，核对字节数和 SHA-256，确认无误再解压。完整包包含 Skill、脚本、风格页及全部 57 张样例；只保存一个 `SKILL.md` 不算安装完成。
2. 使用用户当前 Agent 支持的 Skill 安装位置；若宿主没有自动注册入口，可将包放在稳定目录并读取本包 `SKILL.md` 使用。不要假设所有 Agent 都使用同一个隐藏目录。保留已有版本及用户照片、作品，新版本先放独立目录验证。
3. 检查 Python 3.9+ 与 Pillow。存在时直接复用；没有 Python 时，由 Agent 按操作系统从 Python 官方来源安装并验证，遇到必须由本人确认的系统步骤再交接。不要让用户手动抄安装命令。建议用包内虚拟环境安装依赖，不改全局 Python。

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/doctor.py
```

Windows：

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\doctor.py
```

以上在解压根目录执行。后续用同一个环境的 Python 运行所有脚本，文档中的 `python` / `python3` 均指已验证的该解释器。依赖安装需要联网；日常风格浏览不需 Python 或联网，直接打开 `assets/style-wall/index.html`。

4. `doctor.py` 检查全部样例文件的哈希、图像可读性与风格页，不访问模型、不扣费。随后检查 Agent 是否有可用图片生成／编辑工具；按 [生图能力接入](references/image-generation.md) 复用已有工具。可选 OpenAI 接口仅使用用户自己的配置；没有可用能力时明确说明，不能把安装成功当成生图成功。
5. 请用户发这次封面文字和自己的照片。根据当前内容上下文确定内容目录，不询问保存位置。执行 `asset_library.py --content-dir 当前内容目录 photos 图片路径` 自动建库入库，随后按主 Skill 推荐／选择风格、生成、检查和保存。

安装成功报告应包含：版本、实际安装路径、风格页链接、Python／Pillow 检查、生图能力是否可用。真实制作后再确认封面与两面墙的持久文件；包内敏敏图片用于示例，不能作为用户自己的头像或生成身份输入。

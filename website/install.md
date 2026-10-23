# 由 Agent 安装敏敏封面工作室

当前版本 v1.0.1。用户明确请求安装后，读取 [release.json](release.json)，下载其中 `download_url` 指向的完整 ZIP，核对 `bytes` 和 SHA-256 后再解压。网页工具不可用时，用当前宿主可用的命令行 HTTPS 工具获取本文件和 release.json；保留 TLS 校验，不执行远程脚本。一次网络失败不能假装已下载；重试两次仍失败报告具体原因。

示例命令由 Agent 执行，不让用户手抄：

```sh
curl -fL https://tools.minmin11538.cn/covers/release.json -o release.json
```

从元数据读取实际下载地址，不猜造 ZIP 地址或把错误页当安装包。macOS 可用 `shasum -a 256`，Linux 可用 `sha256sum`，Windows 可用 `Get-FileHash -Algorithm SHA256`；均需实际比较文件字节数和哈希。完整包约 150 MB，包含全部 57 张原尺寸封面样例，使用完整下载而非只复制 SKILL.md。

解压后根目录为 `minmin-cover-studio`。读取其中 `SKILL.md` 和 `INSTALL.md`，由 Agent 检查 Python 3.9+、Pillow 与宿主生图能力，在用户当前 Agent 支持的 Skill 位置安装；没有自动注册能力时，把包保存在稳定目录并读取 SKILL.md 继续。已有版本使用独立新目录验证，保留用户配置和作品。

风格页可直接打开包内 `assets/style-wall/index.html`。先运行 `scripts/doctor.py` 检查完整性，然后按包内流程使用用户自己的文字和照片。不要问保存位置，按当前内容上下文传入内容文件夹；第一次上传或制作自动建库，以后自动更新照片墙与封面墙。

实际生成需要宿主的图片生成／编辑工具，或者用户自己的 OpenAI API 配置。优先复用已有能力，不要求所有用户另配密钥；包内不含账号或生图额度。没有生图工具时如实说明已完成安装、尚未完成生图接入。下载页不收集用户照片；生成时参考照片由用户选用的模型服务处理。

[GitHub 源码](https://github.com/mingminwang962-eng/minmin-cover-studio) · [图片使用说明](ASSET-LICENSE.md)

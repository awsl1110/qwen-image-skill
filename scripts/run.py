#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "dashscope>=1.20.0",
#   "requests>=2.31.0",
# ]
# ///
"""
阿里云百炼 Qwen/Wanx 图像 CLI
用法见 SKILL.md

支持功能：
  text2img    文生图
  edit        千问指令编辑（支持多图输入）
  bg          商品背景生成
  inpaint     图像擦除/局部重绘
  outpaint    扩图
  doodle      涂鸦转写实
  poster      创意海报生成
  segment     人物实例分割
  virtualmodel 虚拟模特
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from http import HTTPStatus

# ── 地域限制 ────────────────────────────────────────────────────────────────────

# 以下子命令使用万相（Wanx）模型，仅支持中国内地地域（--region cn）
WANX_CN_ONLY_CMDS = {"bg", "inpaint", "outpaint", "doodle", "poster", "segment", "virtualmodel"}

def assert_cn_region(args):
    """万相系列命令必须使用 CN 地域，否则直接报错退出"""
    if getattr(args, "region", "intl") != "cn":
        cmd = args.cmd
        print(
            f"错误: '{cmd}' 命令使用的万相（Wanx）模型仅在中国内地地域可用。\n"
            "请添加 --region cn 后重试。",
            file=sys.stderr,
        )
        sys.exit(1)

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_api_key(args_key=None):
    key = args_key or os.getenv("DASHSCOPE_API_KEY")
    if not key:
        print("错误: 未找到 API Key。请设置环境变量 DASHSCOPE_API_KEY 或使用 --api-key 参数。", file=sys.stderr)
        sys.exit(1)
    return key

def get_base_url(region="intl"):
    """返回 DashScope base URL"""
    if region == "cn":
        return "https://dashscope.aliyuncs.com/api/v1"
    return "https://dashscope-intl.aliyuncs.com/api/v1"  # 默认新加坡

def poll_task(task_id: str, base_url: str, api_key: str, timeout: int = 300) -> dict:
    """轮询异步任务结果"""
    import requests
    url = f"{base_url}/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("output", {}).get("task_status", "")
        print(f"  状态: {status}", flush=True)
        if status == "SUCCEEDED":
            return data["output"]
        elif status == "FAILED":
            print(f"任务失败: {json.dumps(data, ensure_ascii=False)}", file=sys.stderr)
            sys.exit(1)
        time.sleep(3)
    print("任务超时", file=sys.stderr)
    sys.exit(1)

def post_async(endpoint: str, payload: dict, base_url: str, api_key: str) -> dict:
    """发起异步请求，返回轮询结果"""
    import requests
    url = f"{base_url}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    task_id = data.get("output", {}).get("task_id")
    if not task_id:
        print(f"创建任务失败: {json.dumps(data, ensure_ascii=False)}", file=sys.stderr)
        sys.exit(1)
    print(f"任务已创建 task_id={task_id}", flush=True)
    return poll_task(task_id, base_url, api_key)

def save_images(urls: list, output_dir: str, prefix: str = "output") -> list:
    """下载并保存图片，返回本地路径列表"""
    import requests
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved = []
    ts = time.strftime("%Y%m%d-%H%M%S")
    for i, url in enumerate(urls):
        ext = url.split("?")[0].rsplit(".", 1)[-1] if "." in url.split("?")[0].split("/")[-1] else "png"
        fname = f"{ts}-{prefix}-{i+1}.{ext}"
        path = str(Path(output_dir) / fname)
        img = requests.get(url, timeout=60).content
        with open(path, "wb") as f:
            f.write(img)
        saved.append(path)
        print(f"已保存: {path}")
    return saved

def extract_image_urls(output: dict) -> list:
    """从 API 返回结果中提取图片 URL"""
    urls = []
    # wanx 异步接口
    for item in output.get("results", []):
        if item.get("url"):
            urls.append(item["url"])
    # 海报接口字段名不同
    for item in output.get("render_urls", []):
        urls.append(item)
    return urls


# ── 功能实现 ────────────────────────────────────────────────────────────────────

def cmd_text2img(args, api_key, base_url):
    """文生图：qwen-image-2.0 系列用同步接口（MultiModalConversation），其余用异步接口（ImageSynthesis）"""
    import dashscope
    dashscope.base_http_api_url = base_url

    model = args.model or "qwen-image-2.0-pro"
    print(f"文生图中 model={model} …")

    # qwen-image-2.0 系列必须使用同步接口（MultiModalConversation）
    if model.startswith("qwen-image-2.0"):
        from dashscope import MultiModalConversation
        default_size = "2048*2048"
        response = MultiModalConversation.call(
            api_key=api_key,
            model=model,
            messages=[{"role": "user", "content": [{"text": args.prompt}]}],
            result_format="message",
            stream=False,
            watermark=False,
            prompt_extend=not args.no_extend,
            n=args.n,
            size=args.size or default_size,
            negative_prompt=args.negative_prompt or "",
        )
        if response.status_code != 200:
            print(f"错误: {response.status_code} {response.message}", file=sys.stderr)
            sys.exit(1)
        output_content = response.output.choices[0].message.content
        urls = [item["image"] for item in output_content if item.get("image")]
    else:
        # qwen-image-plus / qwen-image / qwen-image-max 使用异步接口（SDK 自动轮询）
        from dashscope import ImageSynthesis
        default_size = "1328*1328"
        rsp = ImageSynthesis.call(
            api_key=api_key,
            model=model,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt or "",
            n=args.n,
            size=args.size or default_size,
            prompt_extend=not args.no_extend,
            watermark=False,
        )
        if rsp.status_code != HTTPStatus.OK:
            print(f"错误: {rsp.status_code} {rsp.code} {rsp.message}", file=sys.stderr)
            sys.exit(1)
        urls = [r.url for r in rsp.output.results]

    return save_images(urls, args.output_dir, "text2img")


def cmd_edit(args, api_key, base_url):
    """千问图像编辑（单图/多图 + 指令）"""
    import dashscope
    dashscope.base_http_api_url = base_url
    from dashscope import MultiModalConversation

    model = args.model or "qwen-image-edit-max"
    images = args.images or []
    content = [{"image": img} for img in images]
    content.append({"text": args.prompt})

    print(f"图像编辑中 model={model} …")
    call_kwargs = dict(
        api_key=api_key,
        model=model,
        messages=[{"role": "user", "content": content}],
        result_format="message",
        stream=False,
        watermark=False,
        prompt_extend=not args.no_extend,
        n=args.n,
    )
    if args.size:
        call_kwargs["size"] = args.size
    response = MultiModalConversation.call(**call_kwargs)
    if response.status_code != 200:
        print(f"错误: {response.status_code} {response.message}", file=sys.stderr)
        sys.exit(1)
    output_content = response.output.choices[0].message.content
    urls = [item["image"] for item in output_content if item.get("image")]
    return save_images(urls, args.output_dir, "edit")


def cmd_bg(args, api_key, base_url):
    """商品背景生成（wanx-background-generation-v2）【仅限中国内地地域】"""
    assert_cn_region(args)
    if not args.image:
        print("错误: --image 必填（RGBA 透明通道图片 URL）", file=sys.stderr)
        sys.exit(1)
    payload = {
        "model": "wanx-background-generation-v2",
        "input": {
            "base_image_url": args.image,
            "prompt": args.prompt or "",
        },
        "parameters": {
            "n": args.n,
            "model_version": args.model_version or "v3",
        },
    }
    if args.ref_image:
        payload["input"]["ref_image_url"] = args.ref_image
    print("商品背景生成中 …")
    output = post_async("services/aigc/background-generation/generation", payload, base_url, api_key)
    urls = extract_image_urls(output)
    return save_images(urls, args.output_dir, "bg")


def cmd_inpaint(args, api_key, base_url):
    """图像擦除补全 / 局部重绘（wanx2.1-imageedit）【仅限中国内地地域】"""
    assert_cn_region(args)
    if not args.image:
        print("错误: --image 必填", file=sys.stderr)
        sys.exit(1)
    has_mask = bool(args.mask)
    function = "description_edit_with_mask" if has_mask else "inpainting"
    input_data = {
        "function": function,
        "prompt": args.prompt or "",
        "base_image_url": args.image,
    }
    if has_mask:
        input_data["mask_image_url"] = args.mask
    payload = {
        "model": "wanx2.1-imageedit",
        "input": input_data,
        "parameters": {"n": args.n, "prompt_extend": not args.no_extend},
    }
    label = "局部重绘" if has_mask else "图像擦除"
    print(f"{label}中 function={function} …")
    output = post_async("services/aigc/image2image/image-synthesis", payload, base_url, api_key)
    urls = extract_image_urls(output)
    return save_images(urls, args.output_dir, "inpaint")


def cmd_outpaint(args, api_key, base_url):
    """扩图/画面扩展（wanx2.1-imageedit）【仅限中国内地地域】"""
    assert_cn_region(args)
    if not args.image:
        print("错误: --image 必填", file=sys.stderr)
        sys.exit(1)
    params = {"n": args.n}
    if args.top:    params["top_expansion"] = args.top
    if args.bottom: params["bottom_expansion"] = args.bottom
    if args.left:   params["left_expansion"] = args.left
    if args.right:  params["right_expansion"] = args.right
    payload = {
        "model": "wanx2.1-imageedit",
        "input": {
            "function": "outpainting",
            "prompt": args.prompt or "",
            "base_image_url": args.image,
        },
        "parameters": params,
    }
    print("扩图中 …")
    output = post_async("services/aigc/image2image/image-synthesis", payload, base_url, api_key)
    urls = extract_image_urls(output)
    return save_images(urls, args.output_dir, "outpaint")


def cmd_doodle(args, api_key, base_url):
    """涂鸦/草图转写实（wanx2.1-imageedit）【仅限中国内地地域】"""
    assert_cn_region(args)
    if not args.image:
        print("错误: --image 必填（线稿/涂鸦图 URL）", file=sys.stderr)
        sys.exit(1)
    payload = {
        "model": "wanx2.1-imageedit",
        "input": {
            "function": "doodle",
            "prompt": args.prompt,
            "base_image_url": args.image,
        },
        "parameters": {"n": args.n, "strength": args.strength or 0.8},
    }
    print("涂鸦转写实中 …")
    output = post_async("services/aigc/image2image/image-synthesis", payload, base_url, api_key)
    urls = extract_image_urls(output)
    return save_images(urls, args.output_dir, "doodle")


def cmd_poster(args, api_key, base_url):
    """创意海报生成（wanx-poster-generation-v1）【仅限中国内地地域】"""
    assert_cn_region(args)
    if not args.title:
        print("错误: --title 必填", file=sys.stderr)
        sys.exit(1)
    input_data = {"title": args.title}
    if args.subtitle:    input_data["sub_title"] = args.subtitle
    if args.body:        input_data["body_text"] = args.body
    if args.style:       input_data["prompt_text_zh"] = args.style
    if args.logo:        input_data["logo_url"] = args.logo
    if args.aux_image:   input_data["auxiliary_image_url"] = args.aux_image
    payload = {
        "model": "wanx-poster-generation-v1",
        "input": input_data,
        "parameters": {"generate_num": args.n},
    }
    print("海报生成中 …")
    output = post_async("services/aigc/wordart/poster", payload, base_url, api_key)
    urls = extract_image_urls(output)
    return save_images(urls, args.output_dir, "poster")


def cmd_segment(args, api_key, base_url):
    """人物实例分割（wanx-segmentation）【仅限中国内地地域】"""
    assert_cn_region(args)
    if not args.image:
        print("错误: --image 必填", file=sys.stderr)
        sys.exit(1)
    payload = {
        "model": "wanx-segmentation",
        "input": {"image_url": args.image},
        "parameters": {"segment_type": args.segment_type or "foreground"},
    }
    print("实例分割中 …")
    output = post_async("services/aigc/image-segmentation/segmentation", payload, base_url, api_key)
    # 分割结果结构不同，直接打印然后尝试下载
    print("分割结果:", json.dumps(output, ensure_ascii=False, indent=2))
    urls = []
    if output.get("mask_url"):     urls.append(output["mask_url"])
    if output.get("rgba_url"):     urls.append(output["rgba_url"])
    if output.get("image_url"):    urls.append(output["image_url"])
    return save_images(urls, args.output_dir, "segment")


def cmd_virtualmodel(args, api_key, base_url):
    """虚拟模特生成（wanx-virtualmodel / virtualmodel-v2）【仅限中国内地地域】"""
    assert_cn_region(args)
    if not args.image:
        print("错误: --image 必填（真人模特商品图 URL）", file=sys.stderr)
        sys.exit(1)
    model = "virtualmodel-v2" if (args.model_version or "v2") == "v2" else "wanx-virtualmodel"
    input_data = {"model_image_url": args.image}
    if args.bg_prompt:    input_data["background_prompt"] = args.bg_prompt
    if args.description:  input_data["model_description"] = args.description
    payload = {
        "model": model,
        "input": input_data,
        "parameters": {"n": args.n},
    }
    print(f"虚拟模特生成中 model={model} …")
    output = post_async("services/aigc/virtualmodel/generation", payload, base_url, api_key)
    urls = extract_image_urls(output)
    return save_images(urls, args.output_dir, "virtualmodel")


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        description="阿里云百炼 Qwen/Wanx 图像 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-key", help="DashScope API Key（可用 DASHSCOPE_API_KEY 环境变量）")
    parser.add_argument("--region", default="intl", choices=["intl", "cn"], help="地域：intl=新加坡（默认），cn=北京")
    parser.add_argument("--output-dir", default=".", help="输出目录（默认当前目录）")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # text2img
    p = sub.add_parser("text2img", help="文生图")
    p.add_argument("--prompt", required=True, help="提示词")
    p.add_argument("--model", default="qwen-image-2.0-pro", help="模型名，默认 qwen-image-2.0-pro")
    p.add_argument("--size", default=None, help="分辨率（2.0系列默认2048*2048，其他系列默认1328*1328）")
    p.add_argument("--n", type=int, default=1, help="生成数量")
    p.add_argument("--negative-prompt", help="负向提示词")
    p.add_argument("--no-extend", action="store_true", help="禁用提示词自动扩写")

    # edit
    p = sub.add_parser("edit", help="千问图像指令编辑（支持 1-3 张输入图）")
    p.add_argument("--prompt", required=True, help="编辑指令")
    p.add_argument("--images", nargs="+", help="输入图 URL（最多 3 张）")
    p.add_argument("--model", default="qwen-image-edit-max", help="模型名，默认 qwen-image-edit-max")
    p.add_argument("--size", default=None, help="分辨率（可选，不指定则由模型决定）")
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--no-extend", action="store_true")

    # bg
    p = sub.add_parser("bg", help="商品背景生成（需 RGBA 图）")
    p.add_argument("--image", required=True, help="RGBA 格式商品图 URL")
    p.add_argument("--prompt", required=True, help="背景描述")
    p.add_argument("--ref-image", help="参考风格图 URL（可选）")
    p.add_argument("--model-version", default="v3", choices=["v2", "v3"])
    p.add_argument("--n", type=int, default=4)

    # inpaint
    p = sub.add_parser("inpaint", help="图像擦除补全 / 局部重绘")
    p.add_argument("--image", required=True, help="原图 URL")
    p.add_argument("--mask", help="蒙版 URL（白色=重绘区域）；省略则自动擦除模式")
    p.add_argument("--prompt", default="", help="重绘描述")
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--no-extend", action="store_true")

    # outpaint
    p = sub.add_parser("outpaint", help="扩图（画面扩展）")
    p.add_argument("--image", required=True, help="原图 URL")
    p.add_argument("--prompt", default="", help="扩展内容描述")
    p.add_argument("--top",    type=int, default=0,   help="向上扩展 px")
    p.add_argument("--bottom", type=int, default=0,   help="向下扩展 px")
    p.add_argument("--left",   type=int, default=0,   help="向左扩展 px")
    p.add_argument("--right",  type=int, default=0,   help="向右扩展 px")
    p.add_argument("--n", type=int, default=1)

    # doodle
    p = sub.add_parser("doodle", help="涂鸦/草图转写实")
    p.add_argument("--image", required=True, help="线稿/涂鸦图 URL")
    p.add_argument("--prompt", required=True, help="描述目标效果")
    p.add_argument("--strength", type=float, default=0.8, help="生成自由度 0-1（越大越脱离原稿）")
    p.add_argument("--n", type=int, default=1)

    # poster
    p = sub.add_parser("poster", help="创意海报生成")
    p.add_argument("--title", required=True, help="主标题")
    p.add_argument("--subtitle", help="副标题")
    p.add_argument("--body", help="正文内容")
    p.add_argument("--style", help="风格描述（中文）")
    p.add_argument("--logo", help="Logo 图 URL")
    p.add_argument("--aux-image", help="辅助商品图 URL")
    p.add_argument("--n", type=int, default=4)

    # segment
    p = sub.add_parser("segment", help="人物实例分割")
    p.add_argument("--image", required=True, help="图片 URL")
    p.add_argument("--segment-type", default="foreground", choices=["foreground", "person", "all"])

    # virtualmodel
    p = sub.add_parser("virtualmodel", help="虚拟模特生成")
    p.add_argument("--image", required=True, help="真人模特商品图 URL")
    p.add_argument("--bg-prompt", help="背景描述")
    p.add_argument("--description", help="模特描述")
    p.add_argument("--model-version", default="v2", choices=["v1", "v2"])
    p.add_argument("--n", type=int, default=4)

    return parser


HANDLERS = {
    "text2img":    cmd_text2img,
    "edit":        cmd_edit,
    "bg":          cmd_bg,
    "inpaint":     cmd_inpaint,
    "outpaint":    cmd_outpaint,
    "doodle":      cmd_doodle,
    "poster":      cmd_poster,
    "segment":     cmd_segment,
    "virtualmodel": cmd_virtualmodel,
}

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    api_key = get_api_key(args.api_key)
    base_url = get_base_url(args.region)
    saved = HANDLERS[args.cmd](args, api_key, base_url)
    print(f"\n完成！共 {len(saved)} 张图片已保存。")

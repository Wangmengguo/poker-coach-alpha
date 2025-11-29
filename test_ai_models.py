from __future__ import annotations

import asyncio

from poker.ai_coach import (
    ALLOWED_MODELS,
    DummyProvider,
    get_ai_provider_from_env,
    set_current_model_alias,
)


async def main() -> None:
    provider = get_ai_provider_from_env()
    if isinstance(provider, DummyProvider):
        print(
            "当前使用的是 DummyProvider（未启用真实网关）。\n"
            "请检查 AI_PROVIDER、OPENAI_API_KEY、OPENAI_API_BASE（或 OPENAI_API_URL）"
            "等环境变量是否正确配置到你的第三方 OpenAI 兼容网关。"
        )
        return

    print(f"Using provider: {provider.__class__.__name__}")
    prompt = "用一句简短的话给 HERO 提一条扑克建议。"

    for alias in sorted(ALLOWED_MODELS.keys()):
        set_current_model_alias(alias)
        model_id = ALLOWED_MODELS[alias]
        print(f"\n=== Testing alias: {alias} (model: {model_id}) ===")
        try:
            text = await provider.generate(prompt)
        except Exception as exc:
            print(f"ERROR 调用失败: {exc!r}")
            continue

        if text:
            preview = text.replace("\n", " ")[:160]
            print(f"OK，收到回复：{preview}")
        else:
            print("FAILED：返回空字符串，说明调用网关或解析响应时出现问题。")


if __name__ == "__main__":
    asyncio.run(main())

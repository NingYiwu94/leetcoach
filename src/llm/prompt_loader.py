from app_paths import PROMPTS_DIR


def load_prompt_template(prompt_name):
    prompt_name = str(prompt_name or "").strip()
    if not prompt_name:
        raise ValueError("prompt_name 不能为空")
    if prompt_name.endswith(".md"):
        prompt_name = prompt_name[:-3]

    path = PROMPTS_DIR / f"{prompt_name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise FileNotFoundError(f"Prompt 模板不存在：{path}") from error


def render_prompt(template, variables):
    text = str(template or "")
    variables = variables or {}
    for key, value in variables.items():
        placeholder = "{{" + str(key) + "}}"
        text = text.replace(placeholder, str(value))
    return text

"""验证码生成辅助函数。"""
import random
import re
from collections.abc import Callable

from django.conf import settings
from django.urls import reverse
from PIL import Image, ImageDraw


def _callable_from_string(string_or_callable: str | Callable) -> Callable:
    """根据字符串路径或可调用对象返回对应的可调用对象。

    Args:
        string_or_callable: 可调用对象或以点号分隔的模块路径字符串。

    Returns:
        解析得到的可调用对象。
    """
    if callable(string_or_callable):
        return string_or_callable
    else:
        return getattr(
            __import__(".".join(string_or_callable.split(".")[:-1]), {}, {}, [""]),
            string_or_callable.split(".")[-1],
        )


def get_challenge(generator: str | Callable | None = None) -> Callable:
    """获取验证码挑战生成函数。

    Args:
        generator: 生成函数的字符串路径或可调用对象，为空时使用配置中的默认值。

    Returns:
        验证码挑战生成函数。
    """
    return _callable_from_string(generator or settings.CAPTCHA_CHALLENGE_FUNCT)


def noise_functions() -> map | list:
    """获取验证码噪声函数列表。

    Returns:
        噪声函数的迭代器，若未配置则返回空列表。
    """
    if settings.CAPTCHA_NOISE_FUNCTIONS:
        return map(_callable_from_string, settings.CAPTCHA_NOISE_FUNCTIONS)
    return []


def filter_functions() -> map | list:
    """获取验证码过滤函数列表。

    Returns:
        过滤函数的迭代器，若未配置则返回空列表。
    """
    if settings.CAPTCHA_FILTER_FUNCTIONS:
        return map(_callable_from_string, settings.CAPTCHA_FILTER_FUNCTIONS)
    return []


def math_challenge() -> tuple[str, str]:
    """生成数学运算验证码。

    Returns:
        包含挑战字符串和答案字符串的元组。
    """
    operators = ("+", "*", "-")
    operands = (random.randint(1, 10), random.randint(1, 10))
    operator = random.choice(operators)
    if operands[0] < operands[1] and "-" == operator:
        operands = (operands[1], operands[0])
    challenge = "%d%s%d" % (operands[0], operator, operands[1])
    return (
        "{}=".format(challenge.replace("*", settings.CAPTCHA_MATH_CHALLENGE_OPERATOR)),
        str(eval(challenge)),
    )


def random_char_challenge() -> tuple[str, str]:
    """生成随机字符验证码。

    Returns:
        包含大写挑战字符串和原始小写答案字符串的元组。
    """
    chars, ret = "abcdefghijklmnopqrstuvwxyz", ""
    for i in range(settings.CAPTCHA_LENGTH):
        ret += random.choice(chars)
    return ret.upper(), ret


def unicode_challenge() -> tuple[str, str]:
    """生成 Unicode 字符验证码。

    Returns:
        包含大写挑战字符串和原始答案字符串的元组。
    """
    chars, ret = "äàáëéèïíîöóòüúù", ""
    for i in range(settings.CAPTCHA_LENGTH):
        ret += random.choice(chars)
    return ret.upper(), ret


def get_format_color(color: str) -> tuple | str:
    """将颜色字符串转换为绘图可用的颜色格式。

    Args:
        color: 颜色字符串，支持 rgba 等格式。

    Returns:
        转换后的颜色元组或原始字符串。
    """
    if color.lower().startswith("rgba"):
        colors = re.findall(r"\d+\.?\d*", color)
        if float(colors[-1]) <= 1:
            colors[-1] = float(colors[-1]) * 255
        color = tuple(map(int, colors))
    return color


def makeimg(size: tuple, color: str) -> Image.Image:
    """创建验证码图片对象。

    Args:
        size: 图片尺寸 (宽, 高)。
        color: 背景颜色字符串。

    Returns:
        创建的 PIL 图片对象。
    """
    if color == "transparent":
        image = Image.new("RGBA", size)
    else:
        if color.lower().startswith("rgba"):
            image = Image.new("RGBA", size, get_format_color(color))
        else:
            image = Image.new("RGB", size, color)
    return image


def noise_arcs(draw: ImageDraw.ImageDraw, image: Image.Image) -> ImageDraw.ImageDraw:
    """在验证码图片上绘制弧线噪声。

    Args:
        draw: 绘图对象。
        image: 图片对象。

    Returns:
        添加噪声后的绘图对象。
    """
    size = image.size
    color = get_format_color(settings.CAPTCHA_FOREGROUND_COLOR)
    draw.arc([-20, -20, size[0], 20], 0, 295, fill=color)
    draw.line(
        [-20, 20, size[0] + 20, size[1] - 20], fill=color
    )
    draw.line([-20, 0, size[0] + 20, size[1]], fill=color)
    return draw


def noise_dots(draw: ImageDraw.ImageDraw, image: Image.Image) -> ImageDraw.ImageDraw:
    """在验证码图片上绘制点状噪声。

    Args:
        draw: 绘图对象。
        image: 图片对象。

    Returns:
        添加噪声后的绘图对象。
    """
    size = image.size
    for p in range(int(size[0] * size[1] * 0.1)):
        draw.point(
            (random.randint(0, size[0]), random.randint(0, size[1])),
            fill=get_format_color(settings.CAPTCHA_FOREGROUND_COLOR),
        )
    return draw


def noise_null(draw: ImageDraw.ImageDraw, image: Image.Image) -> ImageDraw.ImageDraw:
    """空噪声函数，不做任何处理。

    Args:
        draw: 绘图对象。
        image: 图片对象。

    Returns:
        原始绘图对象。
    """
    return draw


def post_smooth(image: Image.Image) -> Image.Image:
    """对验证码图片进行平滑处理。

    Args:
        image: 待处理的图片对象。

    Returns:
        平滑处理后的图片对象。
    """
    from PIL import ImageFilter

    return image.filter(ImageFilter.SMOOTH)


def captcha_image_url(key: str) -> str:
    """返回验证码图片的访问 URL，用于 ajax 刷新等场景。

    Args:
        key: 验证码 hashkey。

    Returns:
        验证码图片的 URL 字符串。
    """
    return reverse("system:captcha-image", args=[key])


def captcha_audio_url(key: str) -> str:
    """返回验证码音频的访问 URL，用于 ajax 刷新等场景。

    Args:
        key: 验证码 hashkey。

    Returns:
        验证码音频的 URL 字符串。
    """
    return reverse("system:captcha-audio", args=[key])
